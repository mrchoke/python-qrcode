import abc
from decimal import Decimal
from typing import TYPE_CHECKING, NamedTuple, Optional

from qrcode.compat.etree import ET
from qrcode.image.styles.moduledrawers.base import QRModuleDrawer

if TYPE_CHECKING:
    from qrcode.image.svg import SvgFragmentImage, SvgPathImage

ANTIALIASING_FACTOR = 4


class Coords(NamedTuple):
    x0: Decimal
    y0: Decimal
    x1: Decimal
    y1: Decimal
    xh: Decimal
    yh: Decimal


class BaseSvgQRModuleDrawer(QRModuleDrawer):
    img: "SvgFragmentImage"
    fill_color: Optional[str] = None

    def __init__(self, *, size_ratio: Decimal = Decimal(1), **kwargs):
        self.size_ratio = size_ratio

        if "fill_color" in kwargs:
            self.fill_color = kwargs.pop("fill_color")

    def initialize(self, *args, **kwargs) -> None:
        super().initialize(*args, **kwargs)
        self.box_delta = (1 - self.size_ratio) * self.img.box_size / 2
        self.box_size = Decimal(self.img.box_size) * self.size_ratio
        self.box_half = self.box_size / 2

        if not self.fill_color:
            self.fill_color = self.img.front_color

    def coords(self, box) -> Coords:
        row, col = box[0]
        x = row + self.box_delta
        y = col + self.box_delta

        return Coords(
            x,
            y,
            x + self.box_size,
            y + self.box_size,
            x + self.box_half,
            y + self.box_half,
        )

    def is_eye_outer(self, row: int, col: int):
        """
        Returns True if the row/col is in the outer eye pattern
        """
        border_width = self.img.border * self.img.box_size
        eye_limit = border_width + (self.img.box_size * 7) + self.img.box_size
        image_width = self.img.pixel_size

        return (
            (row < eye_limit and col < eye_limit)
            or (row < eye_limit and col > image_width - eye_limit)
            or (row > image_width - eye_limit and col < eye_limit)
        )

    def is_eye_center(self, row: int, col: int):
        """
        Returns True if the row/col is in the center of the eye pattern
        """
        border_width = self.img.border * self.img.box_size
        inner_limit = border_width + (self.img.box_size * 4) + self.img.box_size
        image_width = self.img.pixel_size

        return (
            (border_width + self.img.box_size) < row < inner_limit
            and (border_width + self.img.box_size) < col < inner_limit
            or (border_width + self.img.box_size) < row < inner_limit
            and (
                image_width - inner_limit
                <= col
                < image_width - border_width - (self.img.box_size * 2)
            )
            or (
                image_width - inner_limit
                <= row
                < image_width - border_width - (self.img.box_size * 2)
                and (border_width + self.img.box_size) < col < inner_limit
            )
        )


class SvgQRModuleDrawer(BaseSvgQRModuleDrawer):
    tag = "rect"

    def initialize(self, *args, **kwargs) -> None:
        super().initialize(*args, **kwargs)
        self.tag_qname = ET.QName(self.img._SVG_namespace, self.tag)

    def drawrect(self, box, is_active: bool):
        if not is_active:
            return
        self.img._img.append(self.el(box))

    @abc.abstractmethod
    def el(self, box):
        is_inner_eye = self.is_eye_center(box[0][1], box[0][0])
        is_outer_eye = self.is_eye_outer(box[0][1], box[0][0])

        self.fill_color = self.img.front_color


class SvgSquareDrawer(SvgQRModuleDrawer):
    def initialize(self, *args, **kwargs) -> None:
        super().initialize(*args, **kwargs)
        self.unit_size = f"{self.img.units(self.box_size, text=False)}"

    def el(self, box):
        coords = self.coords(box)
        # super().el(box)

        return ET.Element(
            self.tag_qname,  # type: ignore
            x=f"{self.img.units(coords.x0, text=False)}",
            y=f"{self.img.units(coords.y0, text=False)}",
            width=self.unit_size,
            height=self.unit_size,
            fill=self.fill_color,
        )


class SvgCircleDrawer(SvgQRModuleDrawer):
    tag = "circle"

    def initialize(self, *args, **kwargs) -> None:
        super().initialize(*args, **kwargs)
        self.radius = f"{self.img.units(self.box_half, text=False)}"

    def el(self, box):

        coords = self.coords(box)
        return ET.Element(
            self.tag_qname,  # type: ignore
            cx=f"{self.img.units(coords.xh, text=False)}",
            cy=f"{self.img.units(coords.yh, text=False)}",
            r=self.radius,
            fill=self.fill_color,
        )
        # super().el(box)


class SvgPathQRModuleDrawer(BaseSvgQRModuleDrawer):
    img: "SvgPathImage"

    def drawrect(self, box, is_active: bool):
        if not is_active:
            return
        self.img._subpaths.append(self.subpath(box))

    @abc.abstractmethod
    def subpath(self, box) -> str: ...


class SvgPathSquareDrawer(SvgPathQRModuleDrawer):
    def subpath(self, box) -> str:
        coords = self.coords(box)
        x0 = self.img.units(coords.x0, text=False)
        y0 = self.img.units(coords.y0, text=False)
        x1 = self.img.units(coords.x1, text=False)
        y1 = self.img.units(coords.y1, text=False)

        return f"M{x0},{y0}H{x1}V{y1}H{x0}z"


class SvgPathCircleDrawer(SvgPathQRModuleDrawer):
    def initialize(self, *args, **kwargs) -> None:
        super().initialize(*args, **kwargs)

    def subpath(self, box) -> str:
        coords = self.coords(box)
        x0 = self.img.units(coords.x0, text=False)
        yh = self.img.units(coords.yh, text=False)
        h = self.img.units(self.box_half - self.box_delta, text=False)
        x1 = self.img.units(coords.x1, text=False)

        # rx,ry is the centerpoint of the arc
        # 1? is the x-axis-rotation
        # 2? is the large-arc-flag
        # 3? is the sweep flag
        # x,y is the point the arc is drawn to

        return f"M{x0},{yh}A{h},{h} 0 0 0 {x1},{yh}A{h},{h} 0 0 0 {x0},{yh}z"


class SveBlankDrawer(SvgQRModuleDrawer):
    def initialize(self, *args, **kwargs) -> None:
        super().initialize(*args, **kwargs)
        self.unit_size = self.img.units(self.box_size)

    def el(self, box) -> str:
        coords = self.coords(box)
        x0 = self.img.units(coords.x0, text=False)
        x1 = self.img.units(coords.x1, text=False)
        y0 = self.img.units(coords.y0, text=False)
        y1 = self.img.units(coords.y1, text=False)

        path = ET.Element(
            ET.QName("path"),  # type: ignore
            d=f"M{x0},{y0}L{x1},{y0}L{x1},{y1}L{x0},{y1}Z",
            # id="qr-path",
            fill="transparent",
        )

        return path


class SvgDiamonDrawer(SvgQRModuleDrawer):
    def initialize(self, *args, **kwargs) -> None:
        super().initialize(*args, **kwargs)
        self.unit_size = self.img.units(self.box_size)

    def el(self, box) -> str:
        coords = self.coords(box)
        x0 = self.img.units(coords.x0, text=False)
        xh = self.img.units(coords.xh, text=False)
        y0 = self.img.units(coords.y0, text=False)
        y1 = self.img.units(coords.y1, text=False)
        yh = self.img.units(coords.yh, text=False)
        h = self.img.units(self.box_half - self.box_delta, text=False)
        x1 = self.img.units(coords.x1, text=False)

        path = ET.Element(
            ET.QName("path"),  # type: ignore
            d=f"M{x0},{yh}L{xh},{y0}L{x1},{yh}L{xh},{y1}Z",
            # id="qr-path",
            fill=self.fill_color,
        )

        return path
