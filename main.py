from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
import subprocess, tempfile, os, shutil, uvicorn

app = FastAPI()

def overlay_videos_with_audio(base, overlay, output, alpha):
    # Cria o filtro para redimensionar o overlay para o tamanho do vídeo base,
    # ajustar a transparência e sobrepor sobre o vídeo base.
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
        '-map', '0:a',  # Mantém o áudio do vídeo base
        '-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
        '-c:a', 'copy',  # Copia o áudio sem reencodar
        output
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

@app.post("/overlay/")
async def overlay_api(
    video_base: UploadFile = File(...),
    video_overlay: UploadFile = File(...),
    transparencia: float = 0.05,
    background_tasks: BackgroundTasks = None
):
    temp_dir = tempfile.mkdtemp()
    base_path = os.path.join(temp_dir, 'base.mp4')
    overlay_path = os.path.join(temp_dir, 'overlay.mp4')
    output_path = os.path.join(temp_dir, 'output.mp4')
    
    # Salva os vídeos enviados na pasta temporária
    with open(base_path, "wb") as f:
        f.write(await video_base.read())
    with open(overlay_path, "wb") as f:
        f.write(await video_overlay.read())
    
    try:
        overlay_videos_with_audio(base_path, overlay_path, output_path, transparencia)
        if background_tasks:
            background_tasks.add_task(shutil.rmtree, temp_dir)
        return FileResponse(output_path, media_type='video/mp4', filename='output.mp4')
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return {"error": str(e)}

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8010)
