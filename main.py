from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool
from moviepy import VideoFileClip, CompositeVideoClip  # import simplificado para v2.x
import tempfile
import os
import uvicorn

app = FastAPI()

def overlay_videos_with_audio(video_base_path, video_overlay_path, output_path, transparencia):
    # Carregar os clipes de vídeo usando MoviePy
    base_clip = VideoFileClip(video_base_path)
    overlay_clip = VideoFileClip(video_overlay_path)
    
    # Ajustar a duração do overlay para ser igual à duração do vídeo base
    overlay_resized = overlay_clip.resized(base_clip.size)
    overlay_resized = overlay_resized.with_duration(base_clip.duration)
    
    # Combinar os vídeos com transparência (caso necessário)
    video_combined = CompositeVideoClip([
        base_clip, 
        overlay_resized.with_opacity(transparencia)
    ])
    
    # Seleciona o áudio: prioriza o do vídeo base e, se não existir, usa o do overlay
    if base_clip.audio:
        audio = base_clip.audio
    elif overlay_clip.audio:
        audio = overlay_clip.audio
    else:
        audio = None
    
    # Define o áudio para o vídeo final, se presente
    if audio:
        video_combined = video_combined.with_audio(audio)
    
    # Escrever o arquivo final com parâmetros otimizados para acelerar a geração
    video_combined.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        threads=12,              # utiliza múltiplas threads conforme a capacidade da máquina
        preset="ultrafast",      # acelera a codificação (pode aumentar o tamanho do arquivo)
        ffmpeg_params=["-crf", "28"],  # ajusta a qualidade para reduzir o tempo de processamento
        logger=None              # desativa logs detalhados para diminuir overhead
    )

@app.post("/overlay/")
async def overlay_api(
    background_tasks: BackgroundTasks,
    video_base: UploadFile = File(...), 
    video_overlay: UploadFile = File(...), 
    transparencia: float = 0.05
):
    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')
    temp_output_video = tempfile.mktemp(suffix='.mp4')
    
    # Salva os arquivos temporariamente
    with open(temp_video_base, "wb") as f:
        f.write(await video_base.read())
    with open(temp_video_overlay, "wb") as f:
        f.write(await video_overlay.read())
    
    try:
        # Executa a função de processamento em uma thread separada
        await run_in_threadpool(
            overlay_videos_with_audio, 
            temp_video_base, 
            temp_video_overlay, 
            temp_output_video, 
            transparencia
        )
        # Agenda a remoção dos arquivos temporários após o envio da resposta
        background_tasks.add_task(os.remove, temp_video_base)
        background_tasks.add_task(os.remove, temp_video_overlay)
        background_tasks.add_task(os.remove, temp_output_video)
        return FileResponse(temp_output_video, media_type='video/mp4', filename='output.mp4')
    except Exception as e:
        # Em caso de erro, remove os arquivos imediatamente se existirem
        for file in [temp_video_base, temp_video_overlay, temp_output_video]:
            if os.path.exists(file):
                os.remove(file)
        return {"error": str(e)}

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8010)
