from moviepy.editor import ColorClip, AudioFileClip, CompositeAudioClip

video = ColorClip((100, 100), color=(255,0,0)).set_duration(2)
audio = AudioFileClip("D:\\AI Tools\\Explainer content\\Testing\\assets_demo\\scene_1.mp3").subclip(0, 1)

try:
    video.set_audio(audio).write_videofile("D:\\AI Tools\\Explainer content\\Testing\\test_vid_err.mp4", fps=10, codec="libx264")
    print("Normal worked")
except Exception as e:
    print("Normal failed:", e)

padded_audio = CompositeAudioClip([audio]).set_duration(video.duration)
try:
    video.set_audio(padded_audio).write_videofile("D:\\AI Tools\\Explainer content\\Testing\\test_vid_err2.mp4", fps=10, codec="libx264")
    print("Padded worked")
except Exception as e:
    print("Padded failed:", e)
