from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
from moviepy import VideoFileClip, CompositeVideoClip
import tempfile
import os
import uvicorn

app = FastAPI()

def overlay_videos_with_audio(video_base_path, video_overlay_path, output_path, transparencia):
    base_clip = VideoFileClip(video_base_path)
    overlay_clip = VideoFileClip(video_overlay_path)

    overlay_resized = overlay_clip.resized(base_clip.size).with_duration(base_clip.duration)

    video_combined = CompositeVideoClip([
        base_clip,
        overlay_resized.with_opacity(transparencia)
    ])

    audio = base_clip.audio or overlay_clip.audio

    if audio:
        video_combined = video_combined.with_audio(audio)

    video_combined.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        threads=10,
        preset="ultrafast",
        ffmpeg_params=["-crf", "28", "-threads", "10"],
        temp_audiofile='temp-audio.m4a',
        remove_temp=True,
        logger='bar'
    )

    video_combined.close()
    base_clip.close()
    overlay_clip.close()

@app.post("/overlay/")
async def overlay_api(
    video_base: UploadFile = File(...),
    video_overlay: UploadFile = File(...),
    transparencia: float = 0.05,
    background_tasks: BackgroundTasks = None
):
    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')
    temp_output_video = tempfile.mktemp(suffix='.mp4')

    with open(temp_video_base, "wb") as f:
        f.write(await video_base.read())
    with open(temp_video_overlay, "wb") as f:
        f.write(await video_overlay.read())

    try:
        overlay_videos_with_audio(temp_video_base, temp_video_overlay, temp_output_video, transparencia)
        if background_tasks:
            background_tasks.add_task(os.remove, temp_output_video)
        return FileResponse(temp_output_video, media_type='video/mp4', filename='output.mp4')
    except Exception as e:
        return {"error": str(e)}
    finally:
        for file_path in [temp_video_base, temp_video_overlay]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8010)
