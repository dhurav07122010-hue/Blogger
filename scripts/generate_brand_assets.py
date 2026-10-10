"""
Generate high-fidelity, modern logo and icon assets for the 'Bloggers' application.
Produces:
- frontend/icon.png (512x512)
- frontend/icon.ico (Windows multi-resolution ICO: 16, 24, 32, 48, 64, 128, 256)
- frontend/logo.svg (Vector logo for the UI)
"""
import math
from PIL import Image, ImageDraw, ImageFilter

def create_brand_icon(size=512):
    # Create high-res canvas with RGBA
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Rounded squircle base
    pad = int(size * 0.05)
    r = int(size * 0.22)
    
    # Subtle drop shadow
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle(
        [pad + 8, pad + 16, size - pad - 8, size - pad + 8],
        radius=r,
        fill=(0, 0, 0, 90)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=int(size * 0.04)))
    img = Image.alpha_composite(img, shadow)
    draw = ImageDraw.Draw(img)
    
    # Modern gradient squircle (deep indigo-violet to bright electric cyan/blue)
    # We draw horizontal slice gradients with rounded clipping
    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=r,
        fill=255
    )
    
    gradient = Image.new("RGBA", (size, size))
    gdraw = ImageDraw.Draw(gradient)
    
    # Diagonal gradient colors
    c1 = (37, 99, 235)    # Vibrant Royal Blue #2563eb
    c2 = (124, 58, 237)   # Deep Purple #7c3aed
    c3 = (236, 72, 153)   # Radiant Pink #ec4899
    
    steps = size
    for y in range(steps):
        t = y / steps
        if t < 0.5:
            factor = t * 2
            r_c = int(c1[0] * (1 - factor) + c2[0] * factor)
            g_c = int(c1[1] * (1 - factor) + c2[1] * factor)
            b_c = int(c1[2] * (1 - factor) + c2[2] * factor)
        else:
            factor = (t - 0.5) * 2
            r_c = int(c2[0] * (1 - factor) + c3[0] * factor)
            g_c = int(c2[1] * (1 - factor) + c3[1] * factor)
            b_c = int(c2[2] * (1 - factor) + c3[2] * factor)
        gdraw.line([(0, y), (size, y)], fill=(r_c, g_c, b_c, 255))
        
    # Composite squircle
    img.paste(gradient, (0, 0), mask)
    
    # Inner border glow
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.rounded_rectangle(
        [pad + 3, pad + 3, size - pad - 3, size - pad - 3],
        radius=r - 2,
        outline=(255, 255, 255, 60),
        width=int(size * 0.015)
    )
    img = Image.alpha_composite(img, glow)
    
    # Draw artistic, sleek quill-spark / generative blog symbol
    # Composition:
    # 1. Stylized glowing fountain pen / quill nib angled at 45 degrees
    # 2. Cosmic AI spark / 4-point star emerging from the nib
    # 3. Dynamic content lines below
    
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    
    cx, cy = size * 0.48, size * 0.52
    
    # Stylized Pen Nib / Editorial Emblem (Crisp white + soft cyan shading)
    # Nib body points
    nib_tip = (size * 0.32, size * 0.68)
    nib_top_l = (size * 0.35, size * 0.42)
    nib_shoulder_l = (size * 0.46, size * 0.32)
    nib_center_top = (size * 0.54, size * 0.28)
    nib_shoulder_r = (size * 0.64, size * 0.36)
    nib_top_r = (size * 0.58, size * 0.56)
    
    # Sleek stylized geometric quill / feather
    # Left wing
    odraw.polygon([
        (size * 0.32, size * 0.68),
        (size * 0.32, size * 0.46),
        (size * 0.48, size * 0.30),
        (size * 0.48, size * 0.56),
    ], fill=(255, 255, 255, 240))
    
    # Right wing
    odraw.polygon([
        (size * 0.32, size * 0.68),
        (size * 0.50, size * 0.56),
        (size * 0.66, size * 0.42),
        (size * 0.56, size * 0.70),
    ], fill=(240, 245, 255, 210))
    
    # Feather spine line (cut slit)
    odraw.line([(size * 0.32, size * 0.68), (size * 0.54, size * 0.38)], fill=(30, 41, 59, 230), width=int(size * 0.025))
    
    # Heart hole / aperture circle
    hole_center = (size * 0.44, size * 0.52)
    hr = int(size * 0.035)
    odraw.ellipse([hole_center[0] - hr, hole_center[1] - hr, hole_center[0] + hr, hole_center[1] + hr], fill=(30, 41, 59, 230))
    
    # 4-Point AI Star / Spark on top right (representing intelligence & creativity)
    def draw_spark(center, r_outer, r_inner, color):
        pts = []
        for i in range(8):
            angle = i * (math.pi / 4)
            r_cur = r_outer if i % 2 == 0 else r_inner
            pts.append((center[0] + r_cur * math.cos(angle), center[1] + r_cur * math.sin(angle)))
        odraw.polygon(pts, fill=color)

    # Large AI Spark
    spark_c = (size * 0.68, size * 0.30)
    draw_spark(spark_c, size * 0.16, size * 0.045, (255, 255, 255, 255))
    
    # Secondary mini spark
    spark_c2 = (size * 0.78, size * 0.50)
    draw_spark(spark_c2, size * 0.07, size * 0.02, (255, 255, 255, 220))
    
    # Small tertiary spark
    spark_c3 = (size * 0.32, size * 0.28)
    draw_spark(spark_c3, size * 0.05, size * 0.015, (255, 255, 255, 180))
    
    # Modern wave / publication accent lines at base
    w_y1 = int(size * 0.76)
    w_y2 = int(size * 0.82)
    odraw.rounded_rectangle([size * 0.30, w_y1, size * 0.70, w_y1 + int(size * 0.03)], radius=int(size * 0.015), fill=(255, 255, 255, 190))
    odraw.rounded_rectangle([size * 0.40, w_y2, size * 0.64, w_y2 + int(size * 0.03)], radius=int(size * 0.015), fill=(255, 255, 255, 130))

    img = Image.alpha_composite(img, overlay)
    return img

if __name__ == "__main__":
    icon_512 = create_brand_icon(512)
    
    # Save primary 512x512 icon
    icon_512.save("frontend/icon.png", format="PNG")
    print("Saved frontend/icon.png")
    
    # Save multi-resolution Windows ICO
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon_512.save("frontend/icon.ico", format="ICO", sizes=sizes)
    print("Saved frontend/icon.ico with multi-resolution sizes")
