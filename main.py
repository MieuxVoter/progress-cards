"""
Draw progress image that is sharable on social networks
"""
import argparse
import time
import os
import glob
from typing import Tuple, List, Dict
from io import BytesIO
import math
import cairo
import firebase_admin
from firebase_admin import credentials, firestore, auth
from flask import Flask, render_template


COLLECTION_NAMES = (
    "constitution",
    "seNourrir",
    "seLoger",
    "seDeplacer",
    "consommer",
    "produire",
)


def text_center(ctx, text, center_x, center_y):
    (x, y, width, height, dx, dy) = ctx.text_extents(text)
    ctx.move_to(center_x - width / 2, center_y)
    ctx.show_text(text)


def draw_image(ctx, image, top, left, height, width):
    """Draw a scaled image on a given context."""
    image_surface = cairo.ImageSurface.create_from_png(image)
    # calculate proportional scaling
    img_height = image_surface.get_height()
    img_width = image_surface.get_width()
    width_ratio = float(width) / float(img_width)
    height_ratio = float(height) / float(img_height)
    scale_xy = min(height_ratio, width_ratio)
    # scale image and add it
    ctx.save()

    ctx.translate(left, top)
    ctx.scale(scale_xy, scale_xy)
    ctx.set_source_surface(image_surface)

    ctx.paint()
    ctx.restore()


def draw_progress(
    ctx,
    progress,
    progress_center,
    progress_radius,
    fill=(0, 0, 0),
    line_color=(1, 1, 1),
):
    ctx.arc(*progress_center, progress_radius, 0, math.pi * 2)
    ctx.close_path()
    ctx.set_source_rgb(1, 1, 1)
    ctx.set_line_width(5)
    ctx.fill()

    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.arc(
        *progress_center,
        progress_radius - 7,
        -math.pi / 2,
        math.pi * 2 * progress - math.pi / 2,
    )
    ctx.set_source_rgb(*fill)
    ctx.set_line_width(5)
    ctx.stroke()


def text(ctx, text, x, y):
    ctx.move_to(x, y)
    ctx.show_text(str(text))
    ctx.stroke()


def draw_card(
    name: str,
    progress: float,
    filename: str,
    image_size: Tuple[int, int] = (300, 200),
    rgb: Tuple[float, float, float] = (0.011, 0.701, 0.498),
    progress_center: Tuple[int, int] = (220, 80),
    progress_radius: int = 50,
):
    with cairo.SVGSurface(filename, *image_size) as surface:

        ctx = cairo.Context(surface)
        ctx.scale(1, 1)  # Normalizing the canvas

        pat = cairo.LinearGradient(0.0, 0.0, 0.0, 1.0)
        pat.add_color_stop_rgba(1, *rgb, 1.0)  # First stop, 50% opacity

        ctx.rectangle(0, 0, image_size[0], image_size[1] - 50)
        ctx.set_source(pat)
        ctx.fill()

        draw_progress(
            ctx,
            progress,
            progress_center,
            progress_radius,
            fill=rgb,
            line_color=(1, 1, 1),
        )

        ctx.select_font_face("Roboto", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)

        ctx.set_font_size(25)
        ctx.set_source_rgb(*rgb)
        text(ctx, int(progress * 100), progress_center[0] - 20, progress_center[1] + 7)
        ctx.set_font_size(15)
        text(ctx, " %", progress_center[0] + 10, progress_center[1] + 7)

        ctx.set_source_rgb(0.6, 0.6, 0.6)
        x = image_size[0] / 2
        y = image_size[1] - 30
        text_center(ctx, f"{name} a voté", x, y)
        text_center(ctx, "Et vous ?", x, y + 20)

        draw_image(ctx, "./logo.png", 20, 20, 130, 130)


def fetch_info(
    uid: str, collection_names=COLLECTION_NAMES, num_proposals=149
) -> Tuple[str, float]:
    client = firestore.client()

    user = client.collection("user").document(uid).get().to_dict()
    name = user["name"]
    counter = 0

    for collection_name in collection_names:
        doc = client.collection(collection_name).document(uid).get().to_dict()
        if doc is not None:
            counter += len(doc)

    progress = counter / num_proposals

    return name, progress


def is_card_uptodate(uid: str, max_timestamp: int):
    """
    It assumes that only one card is available
    """
    filenames = list(glob.glob(f"{uid}-*.svg"))
    if len(filenames) == 0:
        return False
    assert len(filenames) == 1, "Please clean up"
    timestamp = int(filenames[0].split("-")[-1][:-4])
    return timestamp > max_timestamp


def is_valid_uid(uid: str):
    return uid.isalnum()


def clean_card(uid):
    filenames = list(glob.glob(f"cards/{uid}-*.svg"))
    latest_file = max(filenames, key=os.path.getctime)
    for filename in filenames:
        if filename != latest_file:
            os.remove(filename)


app = Flask(__name__)
cred = credentials.Certificate(os.environ["FIREBASE_CREDENTIALS"])
firebase_admin.initialize_app(cred)


@app.route("/card/<uid>")
def get_card(uid):
    if not is_valid_uid(uid):
        return "Invalid uid", 400

    timestamp = int(time.time())

    is_card_uptodate(uid, timestamp - 3600)
    name, progress = fetch_info(uid)
    filename = f"cards/{uid}-{timestamp}.svg"
    print(filename)
    draw_card(name, progress, filename)
    clean_card(uid)

    return render_template(
        "opengraph.html",
        title=f"{name} a voté sur {progress} % des mesures sur VoterPourLeClimat.fr. A votre tour !",
        path=filename,
    )
