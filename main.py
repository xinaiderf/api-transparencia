from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
import tempfile
import os
import uvicorn
import av
import cv2
import numpy as np

app = FastAPI()

def overlay_videos_with_audio(video_base_path, video_overlay_path, output_path, transparencia):
    # Abrir containers dos vídeos base e overlay
    base_container = av.open(video_base_path)
    overlay_container = av.open(video_overlay_path)
    output_container = av.open(output_path, mode='w')
    
    # Seleciona o stream de vídeo (e áudio, se houver) do vídeo base
    base_video_stream = next((s for s in base_container.streams if s.type == 'video'), None)
    if base_video_stream is None:
        raise Exception("Não foi possível encontrar stream de vídeo no arquivo base.")
    base_audio_stream = next((s for s in base_container.streams if s.type == 'audio'), None)
    
    # Seleciona o stream de vídeo do overlay
    overlay_video_stream = next((s for s in overlay_container.streams if s.type == 'video'), None)
    if overlay_video_stream is None:
        raise Exception("Não foi possível encontrar stream de vídeo no arquivo overlay.")
    
    # Cria o stream de vídeo de saída com o codec libx264 e define parâmetros
    output_video_stream = output_container.add_stream("libx264", rate=base_video_stream.average_rate)
    output_video_stream.width = base_video_stream.width
    output_video_stream.height = base_video_stream.height
    output_video_stream.pix_fmt = "yuv420p"
    
    # Se houver áudio no vídeo base, cria o stream de áudio de saída com codec AAC
    if base_audio_stream:
        output_audio_stream = output_container.add_stream("aac", rate=base_audio_stream.rate)
        # Em vez de definir channels diretamente, copie o layout do canal, se disponível
        if base_audio_stream.codec_context.channel_layout:
            output_audio_stream.codec_context.channel_layout = base_audio_stream.codec_context.channel_layout
    else:
        output_audio_stream = None

    # Preparar iterador para os frames do overlay
    overlay_frames = overlay_container.decode(video=overlay_video_stream.index)
    last_overlay_frame = None

    # Processa cada frame do stream de vídeo base
    for base_frame in base_container.decode(video=base_video_stream.index):
        try:
            overlay_frame = next(overlay_frames)
            last_overlay_frame = overlay_frame
        except StopIteration:
            # Se os frames do overlay terminarem, usa o último frame disponível
            overlay_frame = last_overlay_frame if last_overlay_frame is not None else base_frame

        # Converte os frames para arrays NumPy (formato RGB)
        base_img = base_frame.to_ndarray(format='rgb24')
        overlay_img = overlay_frame.to_ndarray(format='rgb24')

        # Redimensiona o frame do overlay para o tamanho do base, se necessário
        if overlay_img.shape[:2] != base_img.shape[:2]:
            overlay_img = cv2.resize(overlay_img, (base_img.shape[1], base_img.shape[0]))

        # Combina os frames com a opacidade definida
        blended = cv2.addWeighted(base_img, 1 - transparencia, overlay_img, transparencia, 0)

        # Cria um novo frame de vídeo a partir do frame combinado
        new_frame = av.VideoFrame.from_ndarray(blended, format='rgb24')
        new_frame.pts = base_frame.pts
        new_frame.time_base = base_frame.time_base

        # Codifica e insere o frame no container de saída
        for packet in output_video_stream.encode(new_frame):
            output_container.mux(packet)

    # Finaliza a codificação do vídeo
    for packet in output_video_stream.encode():
        output_container.mux(packet)

    # Se existir áudio, reencoda os frames de áudio do stream base
    if base_audio_stream:
        for audio_frame in base_container.decode(audio=base_audio_stream.index):
            for packet in output_audio_stream.encode(audio_frame):
                output_container.mux(packet)
        for packet in output_audio_stream.encode():
            output_container.mux(packet)

    output_container.close()
    base_container.close()
    overlay_container.close()

@app.post("/overlay/")
async def overlay_api(video_base: UploadFile = File(...), video_overlay: UploadFile = File(...), transparencia: float = 0.05):
    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')
    temp_output_video = tempfile.mktemp(suffix='.mp4')
    
    # Salva os arquivos enviados em temporários
    with open(temp_video_base, "wb") as f:
        f.write(await video_base.read())
    with open(temp_video_overlay, "wb") as f:
        f.write(await video_overlay.read())
    
    try:
        overlay_videos_with_audio(temp_video_base, temp_video_overlay, temp_output_video, transparencia)
        return FileResponse(temp_output_video, media_type='video/mp4', filename='output.mp4')
    except Exception as e:
        return {"error": str(e)}
    finally:
        os.remove(temp_video_base)
        os.remove(temp_video_overlay)
        # Se necessário, implemente rotina para remover o arquivo de saída posteriormente

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8010)
