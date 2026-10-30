"""Build the requested LUMIX wordmark icon; run from the project root on Windows."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

root=Path(__file__).resolve().parents[1]
image=Image.new('RGBA',(512,512),(16,17,20,255));draw=ImageDraw.Draw(image)
font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',118)
draw.text((256,250),'LUMIX',font=font,fill='#f4f4f5',anchor='mm',stroke_width=1)
draw.rounded_rectangle((47,330,465,345),radius=6,fill='#da4444')
image.save(root/'pianji/ui/lumix.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
