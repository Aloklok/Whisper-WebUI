from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
import traceback
font_path='resources/fonts/NotoSansSC-Regular.ttf'
try:
    pdfmetrics.registerFont(TTFont('NotoSansSC', font_path))
    c=canvas.Canvas('test_noto.pdf')
    c.setFont('NotoSansSC',14)
    c.drawString(72,750,'测试中文 Chinese 測試')
    c.save()
    print('OK: test_noto.pdf generated')
except Exception as e:
    traceback.print_exc()
    print('ERROR', e)
