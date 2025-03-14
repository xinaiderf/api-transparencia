from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
import subprocess, tempfile, os, shutil, uvicorn

app = FastAPI()

def has_audio(file_path: str) -> bool:
    """Verifica se o arquivo possui faixa de áudio utilizando ffprobe."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'a',
        '-show_entries', 'stream=codec_type',
        '-of', 'csv=p=0',
        file_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = result.stdout.decode().strip()
    return "audio" in output

def overlay_videos_with_audio(base: str, overlay: str, output: str, alpha: float):
    """Aplica o overlay do vídeo 'overlay' sobre o vídeo base, mantendo o áudio original."""
    # Verifica se o vídeo base possui áudio
    if not has_audio(base):
        raise ValueError("O vídeo base precisa ter faixa de áudio.")

    # Cadeia de filtros utilizando colorchannelmixer para ajustar a transparência
    filter_complex = (
        "[1:v][0:v]scale2ref=w=iw:h=ih[ovr][base];"
        "[ovr]format=rgba,colorchannelmixer=aa={alpha}[ovr1];"
        "[base][ovr1]overlay=0:0,format=yuv420p[v]"
    ).format(alpha=alpha)

    cmd = [
        'ffmpeg', '-y',
        '-i', base,
        '-i', overlay,
        '-filter_complex', filter_complex,
        '-map', '[v]',
        '-map', '0:a',
        '-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
        '-c:a', 'copy',
        output
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        return
    else:
        # Se a primeira tentativa falhar, tenta alternativa com filtro lut
        alt_filter_complex = (
            "[1:v][0:v]scale2ref=w=iw:h=ih[ovr][base];"
            "[ovr]format=rgba,lut=a='val*{alpha}'[ovr1];"
            "[base][ovr1]overlay=0:0,format=yuv420p[v]"
        ).format(alpha=alpha)
        cmd_alt = [
            'ffmpeg', '-y',
            '-i', base,
            '-i', overlay,
            '-filter_complex', alt_filter_complex,
            '-map', '[v]',
            '-map', '0:a',
            '-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
            '-c:a', 'copy',
            output
        ]
        result_alt = subprocess.run(cmd_alt, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result_alt.returncode == 0:
            return
        else:
            error_message = (
                "Erro com colorchannelmixer: " + result.stderr.decode() + "\n" +
                "Erro com lut: " + result_alt.stderr.decode()
            )
            raise subprocess.CalledProcessError(result_alt.returncode, cmd_alt, output=result_alt.stdout, stderr=error_message)

@app.post("/overlay/")
async def overlay_api(
    video_base: UploadFile = File(...),
    video_overlay: UploadFile = File(...),
    transparencia: float = 0.05
):
    temp_dir = tempfile.mkdtemp()
    base_path = os.path.join(temp_dir, 'base.mp4')
    overlay_path = os.path.join(temp_dir, 'overlay.mp4')
    output_path = os.path.join(temp_dir, 'output.mp4')
    
    # Salva os arquivos enviados na pasta temporária
    with open(base_path, "wb") as f:
        f.write(await video_base.read())
    with open(overlay_path, "wb") as f:
        f.write(await video_overlay.read())
    
    try:
        overlay_videos_with_audio(base_path, overlay_path, output_path, transparencia)
        # Agenda a remoção da pasta temporária após o envio do arquivo de saída.
        return FileResponse(
            output_path, 
            media_type='video/mp4', 
            filename='output.mp4',
            background=BackgroundTask(shutil.rmtree, temp_dir)
        )
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return {"error": str(e)}

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8010)
