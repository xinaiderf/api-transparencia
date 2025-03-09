from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
import cv2
import numpy as np
import tempfile
import os
import uvicorn

app = FastAPI()

def overlay_videos(video_base_path, video_overlay_path, output_path):
    cap_base = cv2.VideoCapture(video_base_path)
    cap_overlay = cv2.VideoCapture(video_overlay_path)
    
    fps = cap_base.get(cv2.CAP_PROP_FPS)
    frame_width = int(cap_base.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap_base.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count_base = int(cap_base.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_count_overlay = int(cap_overlay.get(cv2.CAP_PROP_FRAME_COUNT))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))
    
    overlay_frames = []
    while cap_overlay.isOpened():
        ret_overlay, frame_overlay = cap_overlay.read()
        if not ret_overlay:
            break
        overlay_resized = cv2.resize(frame_overlay, (frame_width, frame_height))
        overlay_frames.append(overlay_resized)
    cap_overlay.release()
    
    overlay_len = len(overlay_frames)
    
    for i in range(frame_count_base):
        ret_base, frame_base = cap_base.read()
        if not ret_base:
            break
        
        overlay_frame = overlay_frames[i % overlay_len]  # Loop overlay if shorter
        blended_frame = cv2.addWeighted(frame_base, 1.0, overlay_frame, 0.15, 0)
        out.write(blended_frame)
    
    cap_base.release()
    out.release()

@app.post("/overlay/")
async def overlay_api(video_base: UploadFile = File(...), video_overlay: UploadFile = File(...)):
    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')
    temp_output_video = tempfile.mktemp(suffix='.mp4')
    
    with open(temp_video_base, "wb") as f:
        f.write(await video_base.read())
    with open(temp_video_overlay, "wb") as f:
        f.write(await video_overlay.read())
    
    try:
        overlay_videos(temp_video_base, temp_video_overlay, temp_output_video)
        return FileResponse(temp_output_video, media_type='video/mp4', filename='output.mp4')
    except Exception as e:
        return {"error": str(e)}
    finally:
        os.remove(temp_video_base)
        os.remove(temp_video_overlay)

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8010)
