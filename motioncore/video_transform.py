"""Main-footage projection; coordinates and limits match KlipeVideoTransform."""
import math


def normalize(clip, width, height):
    def number(key, fallback, low, high):
        try:
            value = float(clip.get(key, fallback))
            if not math.isfinite(value):
                value = fallback
        except (TypeError, ValueError):
            value = fallback
        return max(low, min(high, value))

    if clip.get("transformEnabled") is False:
        clip = {}
    base = number("scale", 1, .1, 3)
    return dict(posX=number("posX", 0, -width, width), posY=number("posY", 0, -height, height),
                scaleX=number("scaleX", base, .1, 3), scaleY=number("scaleY", base, .1, 3),
                anchorX=number("anchorX", 0, -width, width), anchorY=number("anchorY", 0, -height, height),
                rotation=number("rotation", 0, -360, 360), pitch=number("pitch", 0, -60, 60),
                yaw=number("yaw", 0, -60, 60), flipX=clip.get("flipX") is True, flipY=clip.get("flipY") is True)


def project_point(transform, width, height, x, y):
    """Project source pixel coordinates around a movable anchor onto the output."""
    t = transform
    r, p, yaw = (math.radians(t[key]) for key in ("rotation", "pitch", "yaw"))
    x = (x - width / 2 - t["anchorX"]) * t["scaleX"] * (-1 if t["flipX"] else 1)
    y = (y - height / 2 - t["anchorY"]) * t["scaleY"] * (-1 if t["flipY"] else 1)
    yp, zp = y * math.cos(p), y * math.sin(p)
    xy, z = x * math.cos(yaw) + zp * math.sin(yaw), -x * math.sin(yaw) + zp * math.cos(yaw)
    xr, yr = xy * math.cos(r) - yp * math.sin(r), xy * math.sin(r) + yp * math.cos(r)
    distance = 4 * math.hypot(width, height) * max(1, t["scaleX"], t["scaleY"])
    q = 1 + z / distance
    return (width / 2 + t["anchorX"] + t["posX"] + xr / q,
            height / 2 + t["anchorY"] + t["posY"] + yr / q)
