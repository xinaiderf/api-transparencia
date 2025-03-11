from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
import tempfile
import os
import uvicorn
import av
import cv2
import numpy as np

app = FastAPI()

def overlay_videos_with_audio(video_base_path, video_overlay_path, output_path, transparência):
    # Abrir os containers dos vídeos (base e overlay) usando PyAV
    base_container = av.open(video_base_path)
    overlay_container = av.open(video_overlay_path)
    output_container = av.open(output_path, mode='w')
    
    # Selecionar stream de vídeo e, se houver, de áudio do vídeo base
    base_video_stream = None
    base_audio_stream = None
    for stream in base_container.streams:
        if stream.type == 'video' and base_video_stream is None:
            base_video_stream = stream
        elif stream.type == 'audio' and base_audio_stream is None:
            base_audio_stream = stream

    # Selecionar o stream de vídeo do overlay
    overlay_video_stream = None
    for stream in overlay_container.streams:
        if stream.type == 'video':
            overlay_video_stream = stream
            break

    if base_video_stream is None or overlay_video_stream is None:
        raise Exception("Não foi possível encontrar streams de vídeo em um dos arquivos.")

    # Cria o stream de vídeo de saída baseado no vídeo base
    output_video_stream = output_container.add_stream(template=base_video_stream)
    
    # Se o vídeo base possuir áudio, adiciona o stream de áudio de saída
    if base_audio_stream:
        output_audio_stream = output_container.add_stream(template=base_audio_stream)
    else:
        output_audio_stream = None

    # Preparar iterador para os frames do overlay
    overlay_frames = overlay_container.decode(video=overlay_video_stream.index)
    last_overlay_frame = None

    # Processa cada frame do vídeo base
    for base_frame in base_container.decode(video=base_video_stream.index):
        try:
            overlay_frame = next(overlay_frames)
            last_overlay_frame = overlay_frame
        except StopIteration:
            # Se os frames do overlay terminarem, utiliza o último frame disponível
            if last_overlay_frame is None:
                overlay_frame = base_frame
            else:
                overlay_frame = last_overlay_frame

        # Converte os frames para arrays NumPy (formato RGB)
        base_img = base_frame.to_ndarray(format='rgb24')
        overlay_img = overlay_frame.to_ndarray(format='rgb24')

        # Redimensiona o frame do overlay para o tamanho do frame base, se necessário
        if overlay_img.shape[:2] != base_img.shape[:2]:
            overlay_img = cv2.resize(overlay_img, (base_img.shape[1], base_img.shape[0]))
        
        # Combina as imagens: o overlay é aplicado com a opacidade definida
        blended = cv2.addWeighted(base_img, 1 - transparência, overlay_img, transparência, 0)
        
        # Cria um novo frame de vídeo a partir da imagem combinada
        new_frame = av.VideoFrame.from_ndarray(blended, format='rgb24')
        new_frame.pts = base_frame.pts
        new_frame.time_base = base_frame.time_base
        
        # Codifica o novo frame e o insere no container de saída
        for packet in output_video_stream.encode(new_frame):
            output_container.mux(packet)
    
    # Finaliza o encoder de vídeo
    for packet in output_video_stream.encode():
        output_container.mux(packet)
    
    # Se houver áudio no vídeo base, copia os pacotes de áudio para o vídeo final
    if base_audio_stream:
        for packet in base_container.demux(base_audio_stream):
            if packet.dts is None:
                continue
            output_container.mux(packet)
    
    output_container.close()
    base_container.close()
    overlay_container.close()

@app.post("/overlay/")
async def overlay_api(video_base: UploadFile = File(...), video_overlay: UploadFile = File(...), transparência: float = 0.05):
    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')
    temp_output_video = tempfile.mktemp(suffix='.mp4')
    
    # Salva os vídeos enviados em arquivos temporários
    with open(temp_video_base, "wb") as f:
        f.write(await video_base.read())
    with open(temp_video_overlay, "wb") as f:
        f.write(await video_overlay.read())
    
    try:
        overlay_videos_with_audio(temp_video_base, temp_video_overlay, temp_output_video, transparência)
        return FileResponse(temp_output_video, media_type='video/mp4', filename='output.mp4')
    except Exception as e:
        return {"error": str(e)}
    finally:
        os.remove(temp_video_base)
        os.remove(temp_video_overlay)
        # Considere remover temp_output_video após o envio ou usar uma rotina de limpeza

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8010)
