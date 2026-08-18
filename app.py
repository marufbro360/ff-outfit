from flask import Flask, request, jsonify, send_file
import requests
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import os

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=10)
session = requests.Session()

# --- Configuration ---
API_KEY = "Maruf"
BACKGROUND_FILENAME = "outfit.png"
IMAGE_TIMEOUT = 8
CANVAS_SIZE = (800, 800)


def fetch_player_info(uid: str, region: str):
    try:
        url = f"https://vip-info.vercel.app/info?uid={uid}&region={region}"
        resp = session.get(url, timeout=IMAGE_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except:
        return None


def fetch_image(url):
    try:
        r = session.get(url, timeout=IMAGE_TIMEOUT)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGBA")
    except:
        return None


@app.route('/outfit-image', methods=['GET'])
def outfit_image():
    uid = request.args.get('uid')
    key = request.args.get('key')
    region = request.args.get('region', 'pk')

    if key != API_KEY:
        return jsonify({'error': 'Invalid API key'}), 401
    if not uid:
        return jsonify({'error': 'Missing uid'}), 400

    data = fetch_player_info(uid, region)
    if not data:
        return jsonify({'error': 'Player not found'}), 500

    outfit_ids = data.get("profileInfo", {}).get("equippedItems", []) or []
    weapon_ids = data.get("playerData", {}).get("weaponSkinShows", []) or []

    # ------- 7 OUTFIT SLOTS -------
    required_starts = ["211", "214", "211", "203", "204", "205", "203"]
    fallback_ids = [
        "211000000", "214000000", "208000000",
        "203000000", "204000000", "205000000",
        "212000000"
    ]

    used_ids = set()

    def get_outfit(idx, code):
        matched = None
        for oid in outfit_ids:
            s = str(oid)
            if s.startswith(code) and s not in used_ids:
                matched = s
                used_ids.add(s)
                break
        if not matched:
            matched = fallback_ids[idx]
        return fetch_image(f"https://iconapi.wasmer.app/{matched}")

    futures = [executor.submit(get_outfit, i, c) for i, c in enumerate(required_starts)]

    weapon_img = None
    if weapon_ids:
        weapon_img = fetch_image(f"https://iconapi.wasmer.app/{weapon_ids[0]}")

    # ------- Background -------
    bg_path = os.path.join(os.path.dirname(__file__), BACKGROUND_FILENAME)
    bg = Image.open(bg_path).convert("RGBA")

    bg_w, bg_h = bg.size
    canvas_w, canvas_h = CANVAS_SIZE

    scale = max(canvas_w / bg_w, canvas_h / bg_h)
    new_w = int(bg_w * scale)
    new_h = int(bg_h * scale)

    bg = bg.resize((new_w, new_h), Image.LANCZOS)

    offset_x = (canvas_w - new_w) // 2
    offset_y = (canvas_h - new_h) // 2

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 255))
    canvas.paste(bg, (offset_x, offset_y), bg)

    # ------- Original Positions -------
    positions = [
        {'x': 350, 'y': 30},
        {'x': 575, 'y': 130},
        {'x': 665, 'y': 350},
        {'x': 575, 'y': 550},
        {'x': 350, 'y': 654},
        {'x': 135, 'y': 570},
        {'x': 135, 'y': 130},
    ]

    # ------- Paste Outfits -------
    for idx, future in enumerate(futures):
        img = future.result()
        if not img:
            continue

        paste_x = offset_x + int(positions[idx]['x'] * scale)
        paste_y = offset_y + int(positions[idx]['y'] * scale)

        size = int(150 * scale)
        img = img.resize((size, size), Image.LANCZOS)
        canvas.paste(img, (paste_x, paste_y), img)

    # ------- Paste Weapon (PERFECT SAME SYSTEM) -------
    if weapon_img:
        size = int(150 * scale)

        weapon_x = offset_x + int(60 * scale)   # LEFT MIDDLE SLOT
        weapon_y = offset_y + int(350 * scale)

        weapon_img = weapon_img.resize((size, size), Image.LANCZOS)
        canvas.paste(weapon_img, (weapon_x, weapon_y), weapon_img)

    output = BytesIO()
    canvas.save(output, format='PNG')
    output.seek(0)

    return send_file(output, mimetype='image/png')


# --- Vercel/Turmix ready: no app.run() ---
# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000)
