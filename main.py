"""
Draw progress image that is sharable on social networks
"""
import argparse
import time
import os
import glob
from typing import Tuple, List, Dict, Optional
from io import BytesIO
import math
import cairo
import firebase_admin
from firebase_admin import credentials, firestore, auth
from flask import Flask, render_template, send_from_directory, abort


COLLECTION_NAMES = (
    "constitution",
    "seNourrir",
    "seLoger",
    "seDeplacer",
    "consommer",
    "produire",
)

class DoesNotExistError(Exception):
    pass


def fill_rectangle(ctx, x, y, w, h, color):
    pat = cairo.LinearGradient(0.0, 0.0, 0.0, 1.0)
    pat.add_color_stop_rgba(1, *color, 1.0)  # First stop, 50% opacity

    ctx.move_to(0, 0)
    ctx.rectangle(x, y, w, h)
    ctx.set_source(pat)
    ctx.fill()


def text_highlight(ctx, text, x, y, highlight, offset=3):
    (_, dy, width, height, _, _) = ctx.text_extents(str(text))
    fill_rectangle(ctx, x - offset, y - offset + dy, width + offset + 5, height + offset, highlight)


def text_center(ctx, text, center_x, center_y, color=None):
    if color is not None:
        ctx.set_source_rgb(*color)
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


def text(ctx, text, x, y, highlight=None, color=None):
    if highlight is not None:
        text_highlight(ctx, text, x, y, highlight)
    if color is not None:
        ctx.set_source_rgb(*color)
    ctx.move_to(x, y)
    ctx.show_text(str(text))
    ctx.stroke()


def draw_card(
    name: str,
    progress: float,
    filename: str,
    image_size: Tuple[int, int] = (300, 200),
    rgb: Tuple[float, float, float] = (0.011, 0.701, 0.498),
    progress_center: Tuple[int, int] = (240, 80),
    progress_radius: int = 50,
):
    dark_green = (0, 0.56, 0.39)
    with cairo.SVGSurface(filename, *image_size) as surface:

        ctx = cairo.Context(surface)
        ctx.scale(1, 1)  # Normalizing the canvas

        fill_rectangle(ctx, 0, 0, image_size[0], image_size[1], rgb)

        ctx.select_font_face("Noto Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)

        # Display progress
        draw_progress(
            ctx,
            progress,
            progress_center,
            progress_radius,
            fill=rgb,
            line_color=(1, 1, 1),
        )
        ctx.set_font_size(25)
        ctx.set_source_rgb(*rgb)
        text(ctx, int(progress * 100), progress_center[0] - 20, progress_center[1] + 7)
        ctx.set_font_size(15)
        text(ctx, " %", progress_center[0] + 10, progress_center[1] + 7)

        # Left-side text
        start = 60
        jump = 25
        text(ctx, str(name).title(), 20, start, highlight=dark_green, color=(1,1,1))
        text(ctx, "a voté pour le Climat", 20, start + jump, highlight=(0, 0.56, 0.39), color=(1,1,1))
        text(ctx, "Pourquoi pas vous ?", 20, start + jump * 2, highlight=(0, 0.56, 0.39), color=(1,1,1))


        # Footer
        ctx.set_source_rgb(0., 0., 0.)
        x = image_size[0] / 2
        y = image_size[1] - 15
        text_center(ctx, "www.VoterPourLeClimat.fr", x, y, color=(1,1,1))

        # draw_image(ctx, "./assets/logo.png", 20, 20, 130, 130)


def fetch_info(
    uid: str, collection_names=COLLECTION_NAMES, num_proposals=149
) -> Tuple[str, float]:
    client = firestore.client()

    user = client.collection("user").document(uid).get().to_dict()
    if user is None:
        raise DoesNotExistError()

    name = user["name"]
    counter = 0

    for collection_name in collection_names:
        doc = client.collection(collection_name).document(uid).get().to_dict()
        if doc is not None:
            counter += len(doc)

    progress = counter / num_proposals

    return name, progress


def find_card(uid: str):
    """
    It assumes that only one card is available
    """
    filenames = list(glob.glob(f"{uid}-*.svg"))
    if len(filenames) == 0:
        return None
    assert len(filenames) == 1, "Please clean up"
    return filenames[0]

def is_card_uptodate(filename: Optional[str], max_timestamp: int):
    if filename is None:
        return False
    timestamp = int(filename.split("-")[-1][:-4])
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


@app.route("/card/<uid>/refresh")
def get_card_with_refresh(uid: str):
    return get_card(uid, refresh=True)

@app.route("/card/<uid>")
def get_card(uid: str, refresh=False):
    if not is_valid_uid(uid):
        return "Invalid uid", 400

    timestamp = int(time.time())
    filename = find_card(uid)

    try:
        name, progress = fetch_info(uid)
    except DoesNotExistError:
        abort(404)

    if refresh or not is_card_uptodate(filename, timestamp - 3600):
        filename = f"{uid}-{timestamp}.svg"
        draw_card(name, progress, f"cards/{filename}")
        clean_card(uid)

    return send_from_directory("cards", filename=filename, as_attachment=False)
