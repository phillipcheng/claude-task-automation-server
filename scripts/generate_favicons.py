#!/usr/bin/env python3
"""
Generate favicon PNG files for the Claude Server website.
Creates 16x16, 32x32, and 180x180 PNG versions of the favicon.
"""

from PIL import Image, ImageDraw
import os

def create_favicon_png(size, output_path):
    """Create a PNG favicon with the specified size."""
    # Create a new image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Define colors
    blue = (59, 130, 246)  # #3b82f6
    dark_blue = (30, 64, 175)  # #1e40af
    white = (255, 255, 255)

    # Calculate proportional sizes
    center = size // 2
    outer_radius = size // 2 - 1
    inner_size = int(size * 0.5)
    inner_start = (size - inner_size) // 2

    # Draw background circle
    draw.ellipse([1, 1, size-1, size-1], fill=blue, outline=dark_blue, width=1)

    # Draw inner white rectangle (CPU chip)
    chip_size = int(size * 0.5)
    chip_start = (size - chip_size) // 2
    chip_end = chip_start + chip_size
    draw.rounded_rectangle(
        [chip_start, chip_start, chip_end, chip_end],
        radius=max(1, size // 16),
        fill=white + (230,)  # Semi-transparent white
    )

    # Draw circuit lines
    line_width = max(1, size // 20)
    line_spacing = chip_size // 4
    for i in range(3):
        y = chip_start + line_spacing + (i * line_spacing)
        if y < chip_end - line_width:
            draw.rectangle(
                [chip_start + 2, y, chip_end - 2, y + line_width],
                fill=blue + (180,)  # Semi-transparent blue
            )

    # Draw central processor dot
    center_radius = max(1, size // 16)
    draw.ellipse(
        [center - center_radius, center - center_radius,
         center + center_radius, center + center_radius],
        fill=blue
    )

    # Draw corner connection points
    corner_radius = max(1, size // 32)
    corners = [
        (chip_start + chip_size // 4, chip_start + chip_size // 4),
        (chip_end - chip_size // 4, chip_start + chip_size // 4),
        (chip_start + chip_size // 4, chip_end - chip_size // 4),
        (chip_end - chip_size // 4, chip_end - chip_size // 4)
    ]

    for corner_x, corner_y in corners:
        draw.ellipse(
            [corner_x - corner_radius, corner_y - corner_radius,
             corner_x + corner_radius, corner_y + corner_radius],
            fill=blue
        )

    # Save the image
    img.save(output_path, 'PNG')
    print(f"Created {output_path} ({size}x{size})")

def main():
    """Generate all favicon sizes."""
    # Get the static directory path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    static_dir = os.path.join(project_root, 'static')

    # Ensure static directory exists
    os.makedirs(static_dir, exist_ok=True)

    # Generate different sizes
    sizes = [
        (16, 'favicon-16x16.png'),
        (32, 'favicon-32x32.png'),
        (180, 'apple-touch-icon.png')  # For iOS
    ]

    for size, filename in sizes:
        output_path = os.path.join(static_dir, filename)
        create_favicon_png(size, output_path)

    # Also create a standard favicon.ico equivalent as PNG
    create_favicon_png(32, os.path.join(static_dir, 'favicon.png'))

    print("\n✅ All favicon PNG files generated successfully!")
    print("Files created:")
    for size, filename in sizes:
        print(f"  - {filename} ({size}x{size})")
    print("  - favicon.png (32x32)")

if __name__ == "__main__":
    main()