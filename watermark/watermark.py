#!/usr/bin/env python
# -*- coding=utf-8 -*-

import os
import piexif
import click
from geopy.geocoders import Nominatim
from PIL import Image, ImageDraw, ImageFont
from pillow_heif import register_heif_opener

register_heif_opener()


def add_watermarks(image, watermarks, margin):
    for i, watermark in enumerate(watermarks):
        font = ImageFont.truetype(watermark.get("font_family"), watermark.get("font_size"))
        text_width, text_height = font.getlength(watermark.get("text")), watermark.get("font_size")

        x = image.width - text_width - margin
        y = image.height - text_height * (len(watermarks) - i) * 1.5 - margin

        draw = ImageDraw.Draw(image)
        draw.text((x - 1, y - 1), watermark.get("text"), font=font, fill=(0, 0, 0, 255))
        draw.text((x + 1, y - 1), watermark.get("text"), font=font, fill=(0, 0, 0, 255))
        draw.text((x - 1, y + 1), watermark.get("text"), font=font, fill=(0, 0, 0, 255))
        draw.text((x + 1, y + 1), watermark.get("text"), font=font, fill=(0, 0, 0, 255))
        draw.text((x, y), watermark.get("text"), font=font, fill=(255, 255, 255, 128))

    return image


def resize_and_crop_image(image_path, desired_width, desired_height):
    # Open the image file
    image = Image.open(image_path)

    # Calculate the aspect ratio of the original image
    aspect_ratio = image.width / image.height

    if aspect_ratio < 1:
        desired_width, desired_height = desired_height, desired_width

    # Calculate the scaling factor
    scale_factor = max(desired_height / image.height, desired_width / image.width)

    # Resize the image
    new_width = int(image.width * scale_factor)
    new_height = int(image.height * scale_factor)
    image = image.resize((new_width, new_height))

    # Calculate the crop coordinates
    left = (new_width - desired_width) // 2
    top = (new_height - desired_height) // 2
    right = left + desired_width
    bottom = top + desired_height

    # Crop the image
    image = image.crop((left, top, right, bottom))

    return image


def gps_to_place(gps_lat, gps_lon, language):

    lat = gps_lat[0][0] / gps_lat[0][1] + gps_lat[1][0] / gps_lat[1][1] / 60 + gps_lat[2][0] / gps_lat[2][1] / 3600
    lon = gps_lon[0][0] / gps_lon[0][1] + gps_lon[1][0] / gps_lon[1][1] / 60 + gps_lon[2][0] / gps_lon[2][1] / 3600

    place_list = []

    try:
        geolocator = Nominatim(
            user_agent="toolbox-watermark",
            timeout=7,
            proxies={"http": "http://127.0.0.1:1080", "https": "http://127.0.0.1:1080"},
        )

        location = geolocator.reverse(f"{lat}, {lon}", language=language)
        address = location.raw.get("address", {})
        print(address)
        
        place_list.append(address.get("country", ""))
        place_list.append(address.get("state", ""))
        place_list.append(address.get("city", ""))
        place_list.append(address.get("town", ""))
        place_list.append(address.get("borough", ""))
        place_list.append(address.get("village", ""))
        place_list.append(address.get("suburb", ""))


    except Exception as e:
        print(e)
    finally:
        if "zh" in language:
            return "·".join([x for x in place_list if x])
        else:
            return ", ".join([x for x in place_list[::-1] if x])


@click.command()
@click.version_option()
@click.argument("input")
@click.option("-i", "--input", prompt="请输入源文件", help="源文件")
@click.option("-o", "--output", help="输出文件")
@click.option("-p", "--place", help="设置拍摄地址")
@click.option("-f", "--fontfamily", default="HeyMoon.ttf", help="指定字体")
@click.option("-s", "--fontsize", default=40, help="指定字体大小", type=int)
@click.option("-m", "--margin", default=40, help="边距", type=int)
@click.option("-t", "--filetype", default="jpg", help="输出文件")
@click.option("-w", "--width", default=3000, help="裁切宽度", type=int)
@click.option("-h", "--height", default=2000, help="裁切高度", type=int)
def main(input, output, fontfamily, fontsize, margin, filetype, width, height, place):
    # Resize and crop the image
    image = resize_and_crop_image(input, width, height)

    # Get the GPS coordinates and shoot time from the EXIF metadata
    exif_dict = piexif.load(image.info["exif"])
    shoot_time = exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal].decode("utf-8").replace(":", "-", 2)

    watermarks = [{"text": shoot_time, "font_family": fontfamily, "font_size": int(fontsize)}]

    if place:
        watermarks.append({"text": place, "font_family": fontfamily, "font_size": int(fontsize)})
    else:
        gps_info = exif_dict.get("GPS", {})
        gps_lat = gps_info.get(piexif.GPSIFD.GPSLatitude, ())
        gps_lon = gps_info.get(piexif.GPSIFD.GPSLongitude, ())
        if gps_lat and gps_lon:
            place_zh = gps_to_place(gps_lat, gps_lon, language="zh")
            place_en = gps_to_place(gps_lat, gps_lon, language="en")
            watermarks.append(
                {
                    "text": place_en,
                    "font_family": fontfamily,
                    "font_size": int(fontsize),
                }
            )
            watermarks.append(
                {
                    "text": place_zh,
                    "font_family": fontfamily,
                    "font_size": int(fontsize),
                }
            )
        else:
            print(f"[{input}] Unknown location.")

    # Add the watermark
    image = add_watermarks(image, watermarks[::-1], int(margin))

    # Save the output image
    if not output:
        output = f"{os.path.splitext(input)[0]}-P.{filetype.upper()}"
    
    print(f"[{output}] {place_zh}")
    image.save(output)


if __name__ == "__main__":
    main()
