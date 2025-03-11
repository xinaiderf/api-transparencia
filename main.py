from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.fx.all import resize  # Importa a função de redimensionamento
import tempfile
import os
import uvicorn

app = FastAPI()

def overlay_videos_with_audio(video_base_path: str, video_overlay_path: str, output_path: str, transparencia: float):
    # Abre os clipes utilizando os gerenciadores de contexto (MoviePy 2.1.2)
    with VideoFileClip(video_base_path) as base_clip, VideoFileClip(video_overlay_path) as overlay_clip:
        # Redimensiona o overlay para o tamanho do vídeo base utilizando a função resize e ajusta sua duração
        overlay_resized = resize(overlay_clip, newsize=base_clip.size).set_duration(base_clip.duration)
        
        # Combina os clipes aplicando a transparência desejada
        video_combined = CompositeVideoClip([base_clip, overlay_resized.set_opacity(transparencia)])
        
        # Seleciona o áudio: utiliza o áudio do vídeo base; se não houver, usa o do overlay
        audio = base_clip.audio if base_clip.audio else overlay_clip.audio
        if audio:
            video_combined = video_combined.set_audio(audio)
        
        # Exporta o vídeo final com parâmetros otimizados para performance
        video_combined.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            threads=os.cpu_count() or 1,
            preset="ultrafast",
            ffmpeg_params=["-crf", "28"],
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            logger=None
        )
        video_combined.close()

@app.post("/overlay/")
async def overlay_api(
    video_base: UploadFile = File(...),
    video_overlay: UploadFile = File(...),
    transparencia: float = 0.05,
    background_tasks: BackgroundTasks = None
):
    # Salva os arquivos de entrada em arquivos temporários
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_base:
        base_path = tmp_base.name
        tmp_base.write(await video_base.read())
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_overlay:
        overlay_path = tmp_overlay.name
        tmp_overlay.write(await video_overlay.read())
    
    # Cria um caminho temporário para o arquivo de saída
    output_path = tempfile.mktemp(suffix=".mp4")
    
    try:
        overlay_videos_with_audio(base_path, overlay_path, output_path, transparencia)
        # Agenda a remoção do arquivo de saída após o envio da resposta
        if background_tasks is not None:
            background_tasks.add_task(os.remove, output_path)
        return FileResponse(output_path, media_type="video/mp4", filename="output.mp4")
    except Exception as e:
        return {"error": str(e)}
    finally:
        # Remove os arquivos temporários de entrada
        for file_path in (base_path, overlay_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8010)
