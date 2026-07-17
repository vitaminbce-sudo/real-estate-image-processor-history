import os
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, ImageEnhance


# ============================================================
# 基本設定
# ============================================================

TARGET_SIZE = (1920, 1440)
JPEG_QUALITY = 95

LOGO_FILENAME = "logo.png"
LOGO_WIDTH_RATIO = 0.16
LOGO_MARGIN_RATIO = 0.035
LOGO_OPACITY = 0.92


# ============================================================
# 補正設定
# ============================================================

ENABLE_AUTO_ROLL_CORRECTION = False

# 自動パース補正は事故防止のためOFF
ENABLE_AUTO_PERSPECTIVE_CORRECTION = False

MAX_ROLL_DEGREES = 4.0
MIN_ROLL_APPLY_DEGREES = 0.35

ROTATION_CROP_MARGIN_BASE = 0.035
ROTATION_CROP_MARGIN_PER_DEGREE = 0.012

TARGET_MID_DARK = 176
TARGET_MID_NORMAL = 170
TARGET_MID_BRIGHT = 164

COLOR_FACTOR = 0.93
CONTRAST_FACTOR = 1.02
SHARPNESS_FACTOR = 1.06


# ============================================================
# 共通関数
# ============================================================

def clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))


def get_app_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def get_logo_path() -> str:
    return os.path.join(get_app_dir(), LOGO_FILENAME)


def ensure_rgb(image: Image.Image) -> Image.Image:
    """
    EXIF回転を反映してRGBに統一。
    """
    image = ImageOps.exif_transpose(image)

    if image.mode == "RGB":
        return image

    if image.mode in ("RGBA", "LA"):
        background = Image.new("RGB", image.size, (255, 255, 255))

        if image.mode == "RGBA":
            alpha = image.getchannel("A")
            background.paste(image.convert("RGBA"), mask=alpha)
        else:
            background.paste(image.convert("RGB"))

        return background

    return image.convert("RGB")


def ensure_rgba(image: Image.Image) -> Image.Image:
    if image.mode == "RGBA":
        return image

    return image.convert("RGBA")


def pil_to_cv(image: Image.Image) -> np.ndarray:
    image = ensure_rgb(image)
    arr = np.array(image)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def cv_to_pil(image_cv: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(image_cv, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


# ============================================================
# 安全な水平補正
# ============================================================

def estimate_roll_angle_cv(image_cv: np.ndarray) -> float:
    """
    HoughLinesPで水平線・垂直線を検出し、軽い傾きを推定する。
    パース補正ではなく、安全な回転補正のみ。
    """
    height, width = image_cv.shape[:2]

    if width <= 0 or height <= 0:
        return 0.0

    small_w = 900

    if width < small_w:
        small = image_cv.copy()
    else:
        scale = small_w / width
        small_h = max(1, int(height * scale))
        small = cv2.resize(image_cv, (small_w, small_h), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    edges = cv2.Canny(gray, 60, 160)

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=80,
        minLineLength=80,
        maxLineGap=12
    )

    if lines is None:
        return 0.0

    candidate_angles = []
    weights = []

    for line in lines:
        x1, y1, x2, y2 = line[0]

        dx = x2 - x1
        dy = y2 - y1

        length = math.hypot(dx, dy)

        if length < 80:
            continue

        angle = math.degrees(math.atan2(dy, dx))

        while angle <= -90:
            angle += 180

        while angle > 90:
            angle -= 180

        # 水平線に近い線
        if abs(angle) <= 12:
            candidate_angles.append(angle)
            weights.append(length)
            continue

        # 垂直線に近い線
        if abs(abs(angle) - 90) <= 12:
            if angle > 0:
                vertical_angle = angle - 90
            else:
                vertical_angle = angle + 90

            candidate_angles.append(vertical_angle)
            weights.append(length)

    if not candidate_angles:
        return 0.0

    angles = np.array(candidate_angles, dtype=np.float32)
    weights = np.array(weights, dtype=np.float32)

    median = float(np.median(angles))
    mask = np.abs(angles - median) < 3.0

    if np.sum(mask) < 3:
        angle = median
    else:
        angle = float(np.average(angles[mask], weights=weights[mask]))

    angle = clamp(angle, -MAX_ROLL_DEGREES, MAX_ROLL_DEGREES)

    if abs(angle) < MIN_ROLL_APPLY_DEGREES:
        return 0.0

    return angle


def rotate_image_without_black(image_cv: np.ndarray, angle: float) -> np.ndarray:
    """
    黒い余白を出さない回転補正。
    白背景で回転し、外周を内側クロップする。
    """
    if abs(angle) < MIN_ROLL_APPLY_DEGREES:
        return image_cv

    height, width = image_cv.shape[:2]
    center = (width / 2, height / 2)

    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])

    new_w = int((height * sin) + (width * cos))
    new_h = int((height * cos) + (width * sin))

    matrix[0, 2] += (new_w / 2) - center[0]
    matrix[1, 2] += (new_h / 2) - center[1]

    rotated = cv2.warpAffine(
        image_cv,
        matrix,
        (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )

    margin_ratio = ROTATION_CROP_MARGIN_BASE + abs(angle) * ROTATION_CROP_MARGIN_PER_DEGREE
    margin_ratio = clamp(margin_ratio, 0.035, 0.090)

    mx = int(new_w * margin_ratio)
    my = int(new_h * margin_ratio)

    if new_w - mx * 2 < 400 or new_h - my * 2 < 400:
        return rotated

    return rotated[my:new_h - my, mx:new_w - mx]


def apply_safe_geometry_correction(image: Image.Image) -> Image.Image:
    """
    画像を壊さない範囲の軽い水平補正。
    """
    if not ENABLE_AUTO_ROLL_CORRECTION:
        return image

    image_cv = pil_to_cv(image)

    angle = estimate_roll_angle_cv(image_cv)

    if angle == 0.0:
        return image

    corrected = rotate_image_without_black(image_cv, angle)

    return cv_to_pil(corrected)


# ============================================================
# 自然な明るさ・白補正
# ============================================================

def luminance_stats(image: Image.Image) -> dict:
    arr = np.asarray(ensure_rgb(image)).astype(np.float32)

    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]

    lum = 0.299 * r + 0.587 * g + 0.114 * b

    return {
        "mean": float(np.mean(lum)),
        "p05": float(np.percentile(lum, 5)),
        "p10": float(np.percentile(lum, 10)),
        "p25": float(np.percentile(lum, 25)),
        "p50": float(np.percentile(lum, 50)),
        "p75": float(np.percentile(lum, 75)),
        "p90": float(np.percentile(lum, 90)),
        "p95": float(np.percentile(lum, 95)),
        "p98": float(np.percentile(lum, 98)),
        "highlight_ratio": float(np.mean(lum > 245)),
        "shadow_ratio": float(np.mean(lum < 45)),
    }


def estimate_white_balance(image: Image.Image):
    """
    白壁・建具を基準に、黄ばみ・赤みを少し抑える。
    """
    arr = np.asarray(ensure_rgb(image)).astype(np.float32)

    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]

    lum = 0.299 * r + 0.587 * g + 0.114 * b
    chroma = np.maximum.reduce([r, g, b]) - np.minimum.reduce([r, g, b])

    mask = (
        (lum > 70) &
        (lum < 235) &
        (chroma < 65)
    )

    if np.sum(mask) < 1000:
        return 1.0, 1.0, 1.0

    mean_r = float(np.mean(r[mask]))
    mean_g = float(np.mean(g[mask]))
    mean_b = float(np.mean(b[mask]))

    target = (mean_r + mean_g + mean_b) / 3.0

    r_mul = target / max(mean_r, 1)
    g_mul = target / max(mean_g, 1)
    b_mul = target / max(mean_b, 1)

    r_mul = clamp(r_mul * 0.99, 0.93, 1.04)
    g_mul = clamp(g_mul, 0.97, 1.04)
    b_mul = clamp(b_mul * 1.01, 0.98, 1.10)

    return r_mul, g_mul, b_mul


def apply_white_balance(image: Image.Image) -> Image.Image:
    r_mul, g_mul, b_mul = estimate_white_balance(image)

    arr = np.asarray(ensure_rgb(image)).astype(np.float32)

    arr[:, :, 0] *= r_mul
    arr[:, :, 1] *= g_mul
    arr[:, :, 2] *= b_mul

    arr = np.clip(arr, 0, 255).astype(np.uint8)

    return Image.fromarray(arr, "RGB")


def build_tone_curve(stats: dict):
    """
    一律Brightnessではなく、画像ごとのトーンカーブで自然に補正。
    """
    p50 = max(stats["p50"], 1)
    p95 = stats["p95"]
    p98 = stats["p98"]
    highlight_ratio = stats["highlight_ratio"]
    shadow_ratio = stats["shadow_ratio"]

    if highlight_ratio > 0.10 or p98 > 250:
        target_mid = 158
        shadow_lift = 0.025
        highlight_compress = 0.42

    elif p95 > 238 or highlight_ratio > 0.04:
        target_mid = TARGET_MID_BRIGHT
        shadow_lift = 0.035
        highlight_compress = 0.34

    elif shadow_ratio > 0.08 or stats["p10"] < 55:
        target_mid = TARGET_MID_DARK
        shadow_lift = 0.070
        highlight_compress = 0.24

    else:
        target_mid = TARGET_MID_NORMAL
        shadow_lift = 0.050
        highlight_compress = 0.26

    gamma = math.log(target_mid / 255.0) / math.log(p50 / 255.0)
    gamma = clamp(gamma, 0.78, 1.06)

    knee = 0.82
    lut = []

    for i in range(256):
        x = i / 255.0

        y = x ** gamma

        # 暗部だけ自然に持ち上げ
        if x < 0.65:
            y += shadow_lift * (((0.65 - x) / 0.65) ** 1.6)

        # 白飛び防止
        if y > knee:
            t = (y - knee) / (1.0 - knee)
            y = knee + (1.0 - knee) * (t ** (1.0 + highlight_compress * 1.8))

        lut.append(int(clamp(round(y * 255), 0, 255)))

    return lut


def apply_tone_curve(image: Image.Image) -> Image.Image:
    stats = luminance_stats(image)
    lut = build_tone_curve(stats)

    return image.point(lut * 3)


def apply_natural_realestate_tone(image: Image.Image) -> Image.Image:
    """
    不動産写真向けの自然補正。
    白飛びを抑えながら、暗部を自然に持ち上げる。
    """
    image = ensure_rgb(image)

    image = apply_white_balance(image)
    image = apply_tone_curve(image)

    image = ImageEnhance.Contrast(image).enhance(CONTRAST_FACTOR)
    image = ImageEnhance.Color(image).enhance(COLOR_FACTOR)
    image = ImageEnhance.Sharpness(image).enhance(SHARPNESS_FACTOR)

    return image


# ============================================================
# リサイズ・クロップ
# ============================================================

def resize_and_center_crop(image: Image.Image, target_size=TARGET_SIZE) -> Image.Image:
    """
    LANCZOSで高品質リサイズ + 中央クロップ。
    """
    target_w, target_h = target_size
    src_w, src_h = image.size

    src_ratio = src_w / src_h
    target_ratio = target_w / target_h

    if src_ratio > target_ratio:
        new_h = target_h
        new_w = int(target_h * src_ratio)
    else:
        new_w = target_w
        new_h = int(target_w / src_ratio)

    image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)

    left = max(0, (new_w - target_w) // 2)
    top = max(0, (new_h - target_h) // 2)
    right = left + target_w
    bottom = top + target_h

    return image.crop((left, top, right, bottom))


# ============================================================
# SUUMOロゴ
# ============================================================

def add_logo_for_suumo(image: Image.Image) -> Image.Image:
    """
    SUUMO用のみ右下にロゴ合成。
    logo.png がなければ何もしない。
    """
    logo_path = get_logo_path()

    if not os.path.exists(logo_path):
        return image

    base = ensure_rgba(image)

    with Image.open(logo_path) as logo:
        logo = ensure_rgba(logo)

        base_w, base_h = base.size

        logo_target_w = int(base_w * LOGO_WIDTH_RATIO)
        logo_ratio = logo.height / logo.width
        logo_target_h = int(logo_target_w * logo_ratio)

        logo = logo.resize(
            (logo_target_w, logo_target_h),
            Image.Resampling.LANCZOS
        )

        if LOGO_OPACITY < 1.0:
            alpha = logo.getchannel("A")
            alpha = alpha.point(lambda p: int(p * LOGO_OPACITY))
            logo.putalpha(alpha)

        margin = int(base_w * LOGO_MARGIN_RATIO)

        x = base_w - logo_target_w - margin
        y = base_h - logo_target_h - margin

        base.alpha_composite(logo, (x, y))

    return base.convert("RGB")


# ============================================================
# 保存・出力パス
# ============================================================

def make_output_filename(input_path: str) -> str:
    stem = Path(input_path).stem
    return f"{stem}.jpg"


def expected_output_paths(input_path: str, property_folder: str) -> dict:
    """
    watcher.py が既存出力の有無を確認するための関数。
    """
    input_path = os.path.abspath(input_path)
    property_folder = os.path.abspath(property_folder)

    filename = make_output_filename(input_path)

    return {
        "HP": os.path.join(property_folder, "HP", filename),
        "SUUMO": os.path.join(property_folder, "SUUMO", filename),
    }


def save_jpeg(image: Image.Image, output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    image = ensure_rgb(image)

    image.save(
        output_path,
        format="JPEG",
        quality=JPEG_QUALITY,
        optimize=True,
        progressive=True,
        subsampling=0
    )


# ============================================================
# メイン処理
# ============================================================

def process_image(input_path: str, property_folder: str):
    """
    watcher.py から呼ばれる唯一の画像処理関数。

    出力:
    - 物件フォルダ/HP/画像名.jpg
    - 物件フォルダ/SUUMO/画像名.jpg
    """
    input_path = os.path.abspath(input_path)
    property_folder = os.path.abspath(property_folder)

    filename = make_output_filename(input_path)

    with Image.open(input_path) as img:
        img = ensure_rgb(img)

        # 1. 安全な水平補正
        img = apply_safe_geometry_correction(img)

        # 2. 1920x1440へ整形
        img = resize_and_center_crop(img, TARGET_SIZE)

        # 3. 自然な明るさ・白補正
        img = apply_natural_realestate_tone(img)

        # HP用：ロゴなし
        hp_output_dir = os.path.join(property_folder, "HP")
        hp_output_path = os.path.join(hp_output_dir, filename)
        save_jpeg(img, hp_output_path)

        # SUUMO用：ロゴあり
        suumo_img = add_logo_for_suumo(img.copy())
        suumo_output_dir = os.path.join(property_folder, "SUUMO")
        suumo_output_path = os.path.join(suumo_output_dir, filename)
        save_jpeg(suumo_img, suumo_output_path)