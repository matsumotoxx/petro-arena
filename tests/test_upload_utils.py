import unittest
from PIL import Image
from io import BytesIO
from components.upload_utils import validate_image

class TestUploadUtils(unittest.TestCase):
    def make_image_bytes(self, fmt="PNG", size=(128, 128), color=(255, 0, 0)):
        img = Image.new("RGB", size, color)
        b = BytesIO()
        img.save(b, format=fmt)
        return b.getvalue()

    def test_valid_png(self):
        data = self.make_image_bytes("PNG", (256, 256))
        ok, info = validate_image(data, "image/png")
        self.assertTrue(ok)
        self.assertIn("width", info)
        self.assertEqual(info["format"], "PNG")

    def test_large_size_rejected(self):
        data = b"x" * (11 * 1024 * 1024)
        ok, info = validate_image(data, "image/png")
        self.assertFalse(ok)
        self.assertIn("excede", info.lower())

    def test_invalid_format(self):
        data = self.make_image_bytes("BMP", (256, 256))
        ok, info = validate_image(data, "image/bmp")
        self.assertFalse(ok)
        self.assertIn("Formato inválido", info)

    def test_large_dimensions(self):
        data = self.make_image_bytes("JPEG", (5000, 5000))
        ok, info = validate_image(data, "image/jpeg")
        self.assertFalse(ok)
        self.assertIn("Dimensões acima", info)

if __name__ == "__main__":
    unittest.main()
