from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
import subprocess, tempfile, os, shutil, uvicorn

app = FastAPI()

def has_audio(file_path: str) -> bool:
    """Verifica se o arquivo possui faixa de áudio utilizando ffprobe."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'a:0',
        '-show_entries', 'stream=codec_type',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        file_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = result.stdout.decode().strip().lower()
    return "audio" in output

def overlay_videos_with_audio(base: str, overlay: str, output: str, alpha: float):
    """
    Aplica o overlay do vídeo 'overlay' sobre o vídeo base.
    Se o vídeo base possuir áudio, o áudio é mantido inalterado;
    caso contrário, uma faixa de áudio silenciosa é adicionada.
    São utilizadas duas abordagens para ajustar a transparência.
    """
    base_has_audio = has_audio(base)
    
    # Construção do filter_complex com colorchannelmixer
    filter_complex = (
        "[1:v][0:v]scale2ref=w=iw:h=ih[ovr][base];"
        "[ovr]format=rgba,colorchannelmixer=aa={alpha}[ovr1];"
        "[base][ovr1]overlay=0:0,format=yuv420p[v]"
    ).format(alpha=alpha)
    
    if base_has_audio:
        # Se o vídeo base possui áudio, usa-o diretamente
        inputs = ['-i', base, '-i', overlay]
        audio_mapping = ['-map', '0:a']
    else:
        # Caso não haja áudio, gera faixa silenciosa
        inputs = ['-i', base, '-i', overlay, '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100']
        audio_mapping = ['-map', '2:a', '-shortest']
    
    cmd = ['ffmpeg', '-y'] + inputs + [
        '-filter_complex', filter_complex,
        '-map', '[v]'
    ] + audio_mapping + [
        '-c:v', 'libx264', '-crf', '23', '-preset', 'fast'
    ]
    if base_has_audio:
        cmd += ['-c:a', 'copy']
    else:
        cmd += ['-c:a', 'aac']
    cmd.append(output)
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        return
    else:
        # Fallback utilizando o filtro lut para ajustar o alpha
        alt_filter_complex = (
            "[1:v][0:v]scale2ref=w=iw:h=ih[ovr][base];"
            "[ovr]format=rgba,lut=a='val*{alpha}'[ovr1];"
            "[base][ovr1]overlay=0:0,format=yuv420p[v]"
        ).format(alpha=alpha)
        if base_has_audio:
            inputs_alt = ['-i', base, '-i', overlay]
            audio_mapping_alt = ['-map', '0:a']
        else:
            inputs_alt = ['-i', base, '-i', overlay, '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100']
            audio_mapping_alt = ['-map', '2:a', '-shortest']
        cmd_alt = ['ffmpeg', '-y'] + inputs_alt + [
            '-filter_complex', alt_filter_complex,
            '-map', '[v]'
        ] + audio_mapping_alt + [
            '-c:v', 'libx264', '-crf', '23', '-preset', 'fast'
        ]
        if base_has_audio:
            cmd_alt += ['-c:a', 'copy']
        else:
            cmd_alt += ['-c:a', 'aac']
        cmd_alt.append(output)
        
        result_alt = subprocess.run(cmd_alt, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result_alt.returncode != 0:
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
    
    # Salva os arquivos recebidos na pasta temporária
    with open(base_path, "wb") as f:
        f.write(await video_base.read())
    with open(overlay_path, "wb") as f:
        f.write(await video_overlay.read())
    
    try:
        overlay_videos_with_audio(base_path, overlay_path, output_path, transparencia)
        # A pasta temporária será removida após o envio do arquivo de saída.
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
