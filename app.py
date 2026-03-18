"""
Adivyon Digital — Invoice Generator Web App
============================================
Run:   python app.py
Open:  http://localhost:5000
"""

import os, io, json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, send_file, jsonify

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate
from reportlab.lib.utils import ImageReader
from PIL import Image as PILImage
import numpy as np

app = Flask(__name__)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH   = os.path.join(BASE_DIR, 'logo_transparent.png')
OUTPUT_DIR  = os.path.join(BASE_DIR, 'output')
COUNTER_FILE= os.path.join(BASE_DIR, 'invoice_counter.json')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Brand colours ──────────────────────────────────────────────────────────
DARK_BG    = colors.HexColor('#2B3240')
CYAN       = colors.HexColor('#00C8D4')
LIGHT_GRAY = colors.HexColor('#F7F9FC')
MID_GRAY   = colors.HexColor('#E2E8F0')
TEXT_DARK  = colors.HexColor('#1A202C')
TEXT_MID   = colors.HexColor('#4A5568')
TEXT_LIGHT = colors.HexColor('#718096')
WHITE      = colors.white
W, H       = A4

FIRM = {
    "name":       "Adivyon Digital",
    "address1":   "A-302 Rudraksh Kasturi Nirvana, Salaiya",
    "address2":   "Bhopal - 462026, Madhya Pradesh, India",
    "phone":      "+91 74155 76155",
    "email":      "manager@adivyondigital.com",
    "website":    "www.adivyondigital.com",
    "pan":        "DMZPP4474B",
    "bank_name":  "State Bank of India",
    "account_no": "00000044916690779",
    "ifsc":       "SBIN0005499",
    "acc_type":   "Current Account",
}

# ── Invoice counter ─────────────────────────────────────────────────────────
def get_next_invoice_number():
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE) as f:
            data = json.load(f)
        num = data.get('last', 0) + 1
    else:
        num = 1
    with open(COUNTER_FILE, 'w') as f:
        json.dump({'last': num}, f)
    year = datetime.now().year
    return f"ADV-{year}-{num:03d}"

def peek_next_invoice_number():
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE) as f:
            data = json.load(f)
        num = data.get('last', 0) + 1
    else:
        num = 1
    year = datetime.now().year
    return f"ADV-{year}-{num:03d}"

# ── Logo loader ─────────────────────────────────────────────────────────────
def get_logo_reader():
    pil  = PILImage.open(LOGO_PATH).convert('RGBA')
    w, h = pil.size
    pil  = pil.crop((int(w*0.25), int(h*0.05), int(w*0.75), int(h*0.95)))
    data = np.array(pil)
    r, g, b = data[:,:,0], data[:,:,1], data[:,:,2]
    mask = (r < 75) & (g < 75) & (b < 90)
    data[mask, 3] = 0
    out  = PILImage.fromarray(data)
    buf  = io.BytesIO()
    out.save(buf, format='PNG')
    buf.seek(0)
    return ImageReader(buf)

# ── Page template ───────────────────────────────────────────────────────────
def draw_page(logo_reader):
    def _draw(c, doc):
        c.saveState()
        c.setFillColor(DARK_BG)
        c.rect(0, H - 36*mm, W, 36*mm, fill=1, stroke=0)
        c.setFillColor(CYAN)
        c.rect(0, H - 37*mm, W, 1.2*mm, fill=1, stroke=0)
        c.drawImage(logo_reader, 10*mm, H - 34*mm, width=55*mm, height=30*mm,
                    preserveAspectRatio=True, mask='auto')
        c.setFillColor(WHITE)
        c.setFont('Helvetica', 7.2)
        rx = W - 13*mm
        for i, line in enumerate([FIRM['address1'], FIRM['address2'],
                                   FIRM['phone'], FIRM['email'], FIRM['website']]):
            c.drawRightString(rx, H - 10*mm - i*4.4*mm, line)
        c.setFillColor(DARK_BG)
        c.rect(0, 0, W, 17*mm, fill=1, stroke=0)
        c.setFillColor(CYAN)
        c.rect(0, 17*mm, W, 0.8*mm, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont('Helvetica-Bold', 7.5)
        c.drawCentredString(W/2, 10.5*mm, 'Thank you for choosing Adivyon Digital!')
        c.setFillColor(colors.HexColor('#94A3B8'))
        c.setFont('Helvetica', 6.5)
        c.drawCentredString(W/2, 6*mm,
            f"{FIRM['website']}  |  {FIRM['email']}  |  {FIRM['phone']}")
        c.restoreState()
    return _draw

class InvoiceDoc(BaseDocTemplate):
    def __init__(self, filename, on_page, **kwargs):
        super().__init__(filename, **kwargs)
        frame = Frame(12*mm, 20*mm, W - 24*mm, H - 48*mm - 20*mm, id='main')
        tmpl  = PageTemplate(id='invoice', frames=[frame], onPage=on_page)
        self.addPageTemplates([tmpl])

def ps(name, **kw):
    return ParagraphStyle(name, **kw)

# ── PDF builder ─────────────────────────────────────────────────────────────
def build_pdf(data):
    logo_reader = get_logo_reader()
    invoice_num = data['invoice_number']
    output_path = os.path.join(OUTPUT_DIR, f"Invoice_{invoice_num}.pdf")

    doc    = InvoiceDoc(output_path, on_page=draw_page(logo_reader), pagesize=A4)
    styles = getSampleStyleSheet()
    value_sm    = ps('vsm',  fontName='Helvetica', fontSize=8.5, textColor=TEXT_DARK, spaceAfter=1)
    terms_style = ps('trms', fontName='Helvetica', fontSize=7.5, textColor=TEXT_MID, leading=12)
    story  = []

    def lbl(txt):
        return Paragraph(f'<font name="Helvetica-Bold" size="8" color="#718096">{txt}</font>', styles['Normal'])

    # Title + Meta
    meta = Table([
        [Paragraph('<font name="Helvetica-Bold" size="8" color="#718096">INVOICE NO.</font>', styles['Normal']),
         Paragraph('<font name="Helvetica-Bold" size="8" color="#718096">DATE</font>',        styles['Normal']),
         Paragraph('<font name="Helvetica-Bold" size="8" color="#718096">DUE DATE</font>',    styles['Normal'])],
        [Paragraph(f'<font name="Helvetica-Bold" size="10" color="#1A202C">{invoice_num}</font>', styles['Normal']),
         Paragraph(f'<font name="Helvetica-Bold" size="10" color="#1A202C">{data["date"]}</font>', styles['Normal']),
         Paragraph(f'<font name="Helvetica-Bold" size="10" color="#00C8D4">{data["due_date"]}</font>', styles['Normal'])],
    ], colWidths=[40*mm, 36*mm, 36*mm])
    meta.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                               ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]))

    title_row = Table([[
        Paragraph('<font name="Helvetica-Bold" size="22" color="#2B3240">INVOICE</font>', styles['Normal']),
        meta,
    ]], colWidths=[80*mm, 106*mm])
    title_row.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(1,0),(1,0),'RIGHT'),
        ('BACKGROUND',(1,0),(1,0),LIGHT_GRAY),('BOX',(1,0),(1,0),0.5,MID_GRAY),
        ('TOPPADDING',(1,0),(1,0),5),('BOTTOMPADDING',(1,0),(1,0),5),
        ('LEFTPADDING',(1,0),(1,0),5),('RIGHTPADDING',(1,0),(1,0),5),
    ]))
    story += [title_row, Spacer(1,4*mm),
              HRFlowable(width='100%', thickness=0.5, color=MID_GRAY), Spacer(1,4*mm)]

    # Bill To / From
    lbl_row = Table([[lbl('BILL TO'), lbl('FROM')]], colWidths=[93*mm, 93*mm])
    lbl_row.setStyle(TableStyle([('BOTTOMPADDING',(0,0),(-1,-1),2)]))
    story.append(lbl_row)

    def addr_block(lines, colW):
        rows = [[Paragraph(l, ps('ah', fontName='Helvetica-Bold', fontSize=10, textColor=TEXT_DARK)
                           if i==0 else ps('ab', fontName='Helvetica', fontSize=8.5, textColor=TEXT_DARK))]
                for i,l in enumerate(lines) if l]
        t = Table(rows, colWidths=[colW])
        t.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),1.5),
                                ('BOTTOMPADDING',(0,0),(-1,-1),1.5),
                                ('LEFTPADDING',(0,0),(-1,-1),0)]))
        return t

    client_lines = [data['client_name']]
    if data.get('client_address'): client_lines.append(data['client_address'])
    if data.get('client_gst'):     client_lines.append(f'GST: {data["client_gst"]}')
    if data.get('client_pan'):     client_lines.append(f'PAN: {data["client_pan"]}')

    firm_lines = [FIRM['name'], FIRM['address1'], FIRM['address2'],
                  f'PAN: {FIRM["pan"]}',
                  f'Bank: {FIRM["bank_name"]}  |  A/C: {FIRM["account_no"]}',
                  f'IFSC: {FIRM["ifsc"]}']

    bill_table = Table([[addr_block(client_lines, 85*mm), addr_block(firm_lines, 85*mm)]],
                       colWidths=[93*mm, 93*mm])
    bill_table.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LEFTPADDING',(0,0),(0,0),5),('LEFTPADDING',(1,0),(1,0),8),
        ('BACKGROUND',(0,0),(0,0),LIGHT_GRAY),
        ('BACKGROUND',(1,0),(1,0),colors.HexColor('#EBF8FF')),
        ('BOX',(0,0),(0,0),0.5,MID_GRAY),
        ('BOX',(1,0),(1,0),0.5,colors.HexColor('#BEE3F8')),
    ]))
    story += [bill_table, Spacer(1,5*mm)]

    # Services table
    def hdr(txt):
        return Paragraph(f'<font color="white"><b>{txt}</b></font>', styles['Normal'])
    def cell(txt, align=TA_LEFT):
        return Paragraph(txt, ps('c', fontName='Helvetica', fontSize=8.5,
                                  textColor=TEXT_DARK, alignment=align))

    tdata = [[hdr('#'), hdr('Description of Service'), hdr('Qty'),
              hdr('Rate (INR)'), hdr('Amount (INR)')]]
    for idx, item in enumerate(data['items'], 1):
        qty    = float(item['qty'])
        rate   = float(item['rate'])
        amount = qty * rate
        tdata.append([cell(str(idx), TA_CENTER), cell(item['description']),
                      cell(str(int(qty)), TA_CENTER),
                      cell(f'{rate:,.2f}', TA_RIGHT),
                      cell(f'{amount:,.2f}', TA_RIGHT)])

    svc = Table(tdata, colWidths=[10*mm, 82*mm, 14*mm, 28*mm, 32*mm], repeatRows=1)
    row_bg = [('BACKGROUND',(0,i),(-1,i), WHITE if i%2==1 else LIGHT_GRAY)
              for i in range(1, len(tdata))]
    svc.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),DARK_BG),
        ('ALIGN',(0,0),(0,-1),'CENTER'),('ALIGN',(2,0),(2,-1),'CENTER'),
        ('ALIGN',(3,0),(4,-1),'RIGHT'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(1,0),(1,-1),6),
        ('GRID',(0,0),(-1,-1),0.4,MID_GRAY),
        ('LINEBELOW',(0,0),(-1,0),1.2,CYAN),
    ] + row_bg))
    story += [svc, Spacer(1,2*mm)]

    # Totals
    subtotal  = sum(float(i['qty']) * float(i['rate']) for i in data['items'])
    apply_gst = data.get('apply_gst', False)
    gst_rate  = float(data.get('gst_rate', 18))
    fmt       = lambda v: f'{v:,.2f}'

    totals_rows = [
        ['','', Paragraph('<font name="Helvetica" size="9" color="#4A5568">Subtotal</font>', styles['Normal']),
                Paragraph(f'<font name="Helvetica" size="9">INR {fmt(subtotal)}</font>',
                          ps('tv1', alignment=TA_RIGHT))],
    ]
    if apply_gst:
        gst_amt = subtotal * gst_rate / 100
        total   = subtotal + gst_amt
        totals_rows.append([
            '','',
            Paragraph(f'<font name="Helvetica" size="9" color="#4A5568">GST @ {int(gst_rate)}%</font>', styles['Normal']),
            Paragraph(f'<font name="Helvetica" size="9">INR {fmt(gst_amt)}</font>', ps('tv2', alignment=TA_RIGHT)),
        ])
    else:
        total = subtotal

    totals_rows.append([
        '','',
        Paragraph('<font name="Helvetica-Bold" size="10" color="white">TOTAL DUE</font>', styles['Normal']),
        Paragraph(f'<font name="Helvetica-Bold" size="10" color="white">INR {fmt(total)}</font>',
                  ps('tv3', alignment=TA_RIGHT)),
    ])
    last = len(totals_rows) - 1
    totals = Table(totals_rows, colWidths=[10*mm, 82*mm, 42*mm, 32*mm])
    totals.setStyle(TableStyle([
        ('ALIGN',(2,0),(3,-1),'RIGHT'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('RIGHTPADDING',(3,0),(3,-1),4),
        ('BACKGROUND',(2,last),(3,last),DARK_BG),
        ('LINEABOVE',(2,last),(3,last),1.2,CYAN),
        ('LEFTPADDING',(2,last),(3,last),6),
    ]))
    story += [totals, Spacer(1,5*mm),
              HRFlowable(width='100%', thickness=0.5, color=MID_GRAY), Spacer(1,4*mm)]

    # Payment + Terms
    bank_rows = Table([
        [Paragraph('<b>Bank Name:</b>',    ps('b1', fontName='Helvetica-Bold', fontSize=8, textColor=TEXT_MID)), Paragraph(FIRM['bank_name'],   value_sm)],
        [Paragraph('<b>Account No.:</b>',  ps('b2', fontName='Helvetica-Bold', fontSize=8, textColor=TEXT_MID)), Paragraph(FIRM['account_no'],  value_sm)],
        [Paragraph('<b>IFSC Code:</b>',    ps('b3', fontName='Helvetica-Bold', fontSize=8, textColor=TEXT_MID)), Paragraph(FIRM['ifsc'],         value_sm)],
        [Paragraph('<b>PAN No.:</b>',      ps('b4', fontName='Helvetica-Bold', fontSize=8, textColor=TEXT_MID)), Paragraph(FIRM['pan'],          value_sm)],
        [Paragraph('<b>Account Type:</b>', ps('b5', fontName='Helvetica-Bold', fontSize=8, textColor=TEXT_MID)), Paragraph(FIRM['acc_type'],     value_sm)],
    ], colWidths=[26*mm, 58*mm])
    bank_rows.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),2),
                                   ('BOTTOMPADDING',(0,0),(-1,-1),2),
                                   ('LEFTPADDING',(0,0),(-1,-1),0)]))

    gst_term = ('5. GST has been applied as per applicable rates.'
                if apply_gst else '5. This is a non-GST invoice.')
    bottom = Table([
        [lbl('PAYMENT DETAILS'), lbl('TERMS &amp; CONDITIONS')],
        [bank_rows,
         Paragraph(
            '1. Payment is due within 15 days of invoice date.<br/>'
            '2. Late payments may attract 2% monthly interest.<br/>'
            '3. All disputes are subject to Bhopal jurisdiction.<br/>'
            '4. Services are non-refundable once delivered.<br/>'
            f'{gst_term}', terms_style)],
    ], colWidths=[93*mm, 93*mm])
    bottom.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,1),(0,1),5),('LEFTPADDING',(1,1),(1,1),8),
        ('BACKGROUND',(0,1),(0,1),LIGHT_GRAY),
        ('BACKGROUND',(1,1),(1,1),colors.HexColor('#FFFBEB')),
        ('BOX',(0,1),(0,1),0.5,MID_GRAY),
        ('BOX',(1,1),(1,1),0.5,colors.HexColor('#FBD38D')),
    ]))
    story += [bottom, Spacer(1,4*mm)]

    # Signature
    sig = Table([[
        '',
        Table([
            [Paragraph('', styles['Normal'])],
            [HRFlowable(width='100%', thickness=0.5, color=MID_GRAY)],
            [Paragraph('<b>Authorised Signatory</b>',
                       ps('sgl', fontName='Helvetica-Bold', fontSize=8, textColor=TEXT_MID, alignment=TA_CENTER))],
            [Paragraph(FIRM['name'],
                       ps('sgn', fontName='Helvetica', fontSize=8, textColor=TEXT_LIGHT, alignment=TA_CENTER))],
        ], colWidths=[55*mm],
        style=TableStyle([('TOPPADDING',(0,0),(-1,-1),2),
                          ('BOTTOMPADDING',(0,0),(-1,-1),2),
                          ('ALIGN',(0,0),(-1,-1),'CENTER')])),
    ]], colWidths=[131*mm, 55*mm])
    story.append(sig)
    doc.build(story)
    return output_path

# ── Routes ──────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    next_num = peek_next_invoice_number()
    today    = datetime.now()
    due      = today + timedelta(days=15)
    return render_template('index.html',
        next_invoice=next_num,
        today=today.strftime('%d %b %Y'),
        due_date=due.strftime('%d %b %Y'))

@app.route('/generate', methods=['POST'])
def generate():
    try:
        form = request.get_json()
        form['invoice_number'] = get_next_invoice_number()
        pdf_path = build_pdf(form)
        filename = os.path.basename(pdf_path)
        return send_file(pdf_path, as_attachment=True,
                         download_name=filename, mimetype='application/pdf')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/peek')
def peek():
    return jsonify({'next': peek_next_invoice_number()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("\n🚀  Adivyon Digital Invoice Generator")
    print(f"    Open http://localhost:{port} in your browser\n")
    app.run(debug=False, host='0.0.0.0', port=port)
