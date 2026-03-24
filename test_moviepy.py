from moviepy.editor import ColorClip

c = ColorClip((100, 100), color=(255,0,0)).set_duration(2)
c2 = c.fl_time(lambda t: min(t, 1.5)).set_duration(2.5)
c2.write_videofile("D:\\AI Tools\\Explainer content\\Testing\\test_vid.mp4", fps=10, codec="libx264")
print("SUCCESS!")
