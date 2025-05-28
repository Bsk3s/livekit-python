from PIL import Image, ImageDraw
import os

# Create assets directory
os.makedirs('assets', exist_ok=True)

# Create a simple app icon (1024x1024)
icon_size = 1024
icon = Image.new('RGBA', (icon_size, icon_size), (99, 102, 241, 255))  # Indigo background
draw = ImageDraw.Draw(icon)

# Draw a simple spiritual symbol (circle with inner design)
center = icon_size // 2
outer_radius = icon_size // 3
inner_radius = icon_size // 6

# Outer circle (white)
draw.ellipse([center-outer_radius, center-outer_radius, center+outer_radius, center+outer_radius], 
             fill=(255, 255, 255, 255), outline=(255, 255, 255, 255), width=10)

# Inner circle (light blue)
draw.ellipse([center-inner_radius, center-inner_radius, center+inner_radius, center+inner_radius], 
             fill=(173, 216, 230, 255), outline=(255, 255, 255, 255), width=5)

# Save icon
icon.save('assets/icon.png')

# Create splash screen (1024x1024)
splash = Image.new('RGBA', (icon_size, icon_size), (99, 102, 241, 255))  # Same indigo background
splash_draw = ImageDraw.Draw(splash)

# Smaller version for splash
splash_radius = icon_size // 6
splash_inner = icon_size // 12

# Outer circle
splash_draw.ellipse([center-splash_radius, center-splash_radius, center+splash_radius, center+splash_radius], 
                   fill=(255, 255, 255, 255), outline=(255, 255, 255, 255), width=8)

# Inner circle
splash_draw.ellipse([center-splash_inner, center-splash_inner, center+splash_inner, center+splash_inner], 
                   fill=(173, 216, 230, 255), outline=(255, 255, 255, 255), width=4)

# Save splash
splash.save('assets/splash.png')

# Create adaptive icon (foreground)
adaptive = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))  # Transparent background
adaptive_draw = ImageDraw.Draw(adaptive)

# White circle with symbol for adaptive icon
adaptive_draw.ellipse([center-outer_radius, center-outer_radius, center+outer_radius, center+outer_radius], 
                     fill=(255, 255, 255, 255), outline=(255, 255, 255, 255), width=10)
adaptive_draw.ellipse([center-inner_radius, center-inner_radius, center+inner_radius, center+inner_radius], 
                     fill=(173, 216, 230, 255), outline=(255, 255, 255, 255), width=5)

adaptive.save('assets/adaptive-icon.png')

# Create favicon (smaller version)
favicon = icon.resize((48, 48), Image.Resampling.LANCZOS)
favicon.save('assets/favicon.png')

print('✅ Created app assets:')
print('   - icon.png (1024x1024)')
print('   - splash.png (1024x1024)')
print('   - adaptive-icon.png (1024x1024)')
print('   - favicon.png (48x48)') 