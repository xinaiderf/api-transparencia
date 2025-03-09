import os
from flask import Flask, request, jsonify
import cv2
import numpy as np
import tempfile

app = Flask(__name__)

def overlay_videos(video_base_path, video_overlay_path, output_path):
    # Carregar os dois vídeos usando OpenCV
    cap_base = cv2.VideoCapture(video_base_path)
    cap_overlay = cv2.VideoCapture(video_overlay_path)
    
    # Obter informações dos vídeos
    fps = cap_base.get(cv2.CAP_PROP_FPS)
    frame_width = int(cap_base.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap_base.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Criar o writer para salvar o vídeo final
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Usando o codec mp4v
    out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))
    
    while cap_base.isOpened() and cap_overlay.isOpened():
        ret_base, frame_base = cap_base.read()
        ret_overlay, frame_overlay = cap_overlay.read()

        if not ret_base or not ret_overlay:
            break

        # Redimensionar o vídeo sobreposto para o mesmo tamanho do vídeo de fundo
        frame_overlay_resized = cv2.resize(frame_overlay, (frame_width, frame_height))

        # Aplica a transparência (15%) no vídeo sobreposto
        frame_overlay_resized = cv2.addWeighted(frame_base, 1.0, frame_overlay_resized, 0.15, 0)

        # Escreve o frame no arquivo de saída
        out.write(frame_overlay_resized)
    
    # Libera os recursos
    cap_base.release()
    cap_overlay.release()
    out.release()
    print(f"Vídeo final gerado em: {output_path}")

@app.route('/overlay', methods=['POST'])
def overlay_api():
    # Verifica se os vídeos foram enviados corretamente
    if 'video_base' not in request.files or 'video_overlay' not in request.files:
        return jsonify({"error": "Os arquivos de vídeo são necessários."}), 400

    video_base = request.files['video_base']
    video_overlay = request.files['video_overlay']

    # Salva os vídeos temporariamente no servidor
    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')
    
    video_base.save(temp_video_base)
    video_overlay.save(temp_video_overlay)

    # Caminho temporário para o vídeo de saída
    temp_output_video = tempfile.mktemp(suffix='.mp4')

    try:
        # Chama a função para sobrepor os vídeos
        overlay_videos(temp_video_base, temp_video_overlay, temp_output_video)

        # Envia o arquivo gerado como resposta
        return jsonify({"message": "Vídeo gerado com sucesso.", "output_video": temp_output_video})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # Remove os arquivos temporários
        os.remove(temp_video_base)
        os.remove(temp_video_overlay)

if __name__ == '__main__':
    app.run(debug=True)
