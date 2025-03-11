from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
import tempfile
import os
import uvicorn

app = FastAPI()

def overlay_videos_with_audio(video_base_path, video_overlay_path, output_path, transparencia):
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
    # Inicializa o GStreamer
    Gst.init(None)
    
    # Cria uma pipeline que:
    # - Lê os dois arquivos de vídeo (base e overlay) com "filesrc" e os decodifica com "decodebin".
    # - Conecta o vídeo base (sink_0) e o vídeo overlay (sink_1) ao compositor.
    #   A propriedade "sink_1::alpha" é definida para ajustar a opacidade do overlay.
    # - O compositor gera o vídeo final, que é convertido, codificado (usando x264 com preset ultrafast)
    #   e multiplexado com o áudio (extraído do vídeo base) em um arquivo MP4.
    pipeline_description = (
        f'filesrc location="{video_base_path}" ! decodebin name=dec_base '
        f'filesrc location="{video_overlay_path}" ! decodebin name=dec_overlay '
        'dec_base. ! queue ! videoconvert ! videoscale ! comp.sink_0 '
        'dec_overlay. ! queue ! videoconvert ! videoscale ! comp.sink_1::alpha=' + str(transparencia) + ' '
        'compositor name=comp ! videoconvert ! x264enc speed-preset=ultrafast ! mp4mux name=mux '
        'dec_base. ! queue ! audioconvert ! audioresample ! mux. '
        'mux. ! filesink location="' + output_path + '"'
    )
    
    pipeline = Gst.parse_launch(pipeline_description)
    pipeline.set_state(Gst.State.PLAYING)
    
    # Aguarda até que a pipeline termine (EOS) ou ocorra algum erro.
    bus = pipeline.get_bus()
    msg = bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE, Gst.MessageType.ERROR | Gst.MessageType.EOS)
    
    pipeline.set_state(Gst.State.NULL)
    
    if msg and msg.type == Gst.MessageType.ERROR:
        err, debug = msg.parse_error()
        raise Exception(f"GStreamer error: {err}: {debug}")

@app.post("/overlay/")
async def overlay_api(
    background_tasks: BackgroundTasks,
    video_base: UploadFile = File(...), 
    video_overlay: UploadFile = File(...), 
    transparencia: float = 0.05
):
    # Cria arquivos temporários para armazenar os vídeos de entrada e saída
    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')
    temp_output_video = tempfile.mktemp(suffix='.mp4')
    
    # Salva os arquivos enviados
    with open(temp_video_base, "wb") as f:
        f.write(await video_base.read())
    with open(temp_video_overlay, "wb") as f:
        f.write(await video_overlay.read())
    
    try:
        # Chama a função que processa os vídeos usando GStreamer
        overlay_videos_with_audio(temp_video_base, temp_video_overlay, temp_output_video, transparencia)
        # Agenda a remoção dos arquivos temporários após envio da resposta
        background_tasks.add_task(os.remove, temp_video_base)
        background_tasks.add_task(os.remove, temp_video_overlay)
        background_tasks.add_task(os.remove, temp_output_video)
        return FileResponse(temp_output_video, media_type='video/mp4', filename='output.mp4')
    except Exception as e:
        # Em caso de erro, remove os arquivos temporários se existirem
        for file in [temp_video_base, temp_video_overlay, temp_output_video]:
            if os.path.exists(file):
                os.remove(file)
        return {"error": str(e)}

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8010)
