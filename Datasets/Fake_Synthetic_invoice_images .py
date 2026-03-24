from PIL import Image, ImageDraw, ImageFont
import random, os, string
from datetime import datetime

#path
base_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(base_dir, "final_invoices_dataset")
os.makedirs(output_dir, exist_ok=True)

#data
names = ["Rahul Sharma","Priya Reddy","Arjun Patel","Sneha Iyer","Amit Verma"]
cities = ["Bangalore","Mumbai","Delhi","Chennai","Hyderabad"]
companies = ["ABC Pvt Ltd","XYZ Traders","Global Mart","Super Store","SKPS Digital"]
items = ["Rice","Sugar","Oil","Milk","Soap"]

def gst():
    return str(random.randint(10,99)) + ''.join(random.choices(string.ascii_uppercase, k=5)) + str(random.randint(1000,9999)) + "F1Z5"

def phone():
    return str(random.randint(7000000000,9999999999))

def date():
    return datetime.now().strftime("%d-%m-%Y")

# ===== FONT =====
def fonts():
    try:
        return (
            ImageFont.truetype("arial.ttf",42),
            ImageFont.truetype("arial.ttf",20),
            ImageFont.truetype("arial.ttf",24)
        )
    except:
        return None,None,None


#advance template
def advanced_invoice(idx, variant):
    title, text, bold = fonts()

    img = Image.new('RGB', (1100, 1400), 'white')
    draw = ImageDraw.Draw(img)

    # layout variation
    table_x_sets = [
        [50, 250, 400, 550, 700, 850],
        [100, 300, 450, 600, 750, 900],
        [70, 270, 420, 570, 720, 870],
        [50, 230, 380, 530, 680, 830],
        [80, 300, 460, 620, 780, 940]
    ]
    x = table_x_sets[variant]

    # header
    draw.text((350,20),"TAX INVOICE",font=title,fill="black")

    draw.text((50,100),f"Invoice No: {random.randint(100000,999999)}",font=text,fill="black")
    draw.text((50,140),f"Date: {date()}",font=text,fill="black")

    draw.text((700,100),random.choice(companies),font=bold,fill="black")
    draw.text((700,130),random.choice(cities),font=text,fill="black")
    draw.text((700,160),"GSTIN: "+gst(),font=text,fill="black")

    # bill / ship
    draw.rectangle((50,220,500,380),outline="black",width=2)
    draw.rectangle((550,220,1000,380),outline="black",width=2)

    for x_pos,title_txt in [(60,"BILL TO"),(560,"SHIP TO")]:
        y=230
        draw.text((x_pos,y),title_txt,font=bold,fill="black"); y+=25
        draw.text((x_pos,y),random.choice(names),font=text,fill="black"); y+=25
        draw.text((x_pos,y),random.choice(cities),font=text,fill="black"); y+=25
        draw.text((x_pos,y),"Phone:"+phone(),font=text,fill="black"); y+=25
        draw.text((x_pos,y),"GST:"+gst(),font=text,fill="black")

    # table
    y = 420
    headers = ["SL","ITEM","QTY","RATE","TAX","TOTAL"]

    for i in range(6):
        draw.text((x[i], y), headers[i], font=bold, fill="black")

    draw.line((40, y+30, 1050, y+30), fill="black", width=2)
    y += 50

    total = 0

    for i in range(5):
        qty = random.randint(1,10)
        rate = random.randint(100,500)
        amt = qty * rate
        tax = amt * 0.18
        final = amt + tax
        total += final

        row = [str(i+1), random.choice(items), str(qty), str(rate), f"{tax:.2f}", f"{final:.2f}"]

        for j in range(6):
            draw.text((x[j], y), row[j], font=text, fill="black")

        draw.line((40, y+30, 1050, y+30), fill="gray")
        y += random.randint(35,45)

    draw.rectangle((40, 410, 1050, y), outline="black", width=2)

    draw.text((700, y+40), f"TOTAL: {total:.2f}", font=bold, fill="black")
    draw.text((50, y+100), "Authorized Signature", font=text, fill="black")

    img.save(os.path.join(output_dir, f"invoice_{idx}.png"))



# INDUSTRIAL TEMPLATE (30 images)
def industrial_invoice(idx):
    title, text, bold = fonts()

    img = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(img)

    # header band
    draw.rectangle((0,0,1200,80), fill="#dfe6e9")
    draw.text((500,20), "Tax Invoice", font=bold, fill="black")

    # company
    draw.text((100,120), random.choice(companies), font=bold, fill="black")
    draw.text((100,150), random.choice(cities), font=text, fill="black")
    draw.text((100,180), "GSTIN: " + gst(), font=text, fill="black")

    # blocks
    draw.rectangle((50,260,600,420), outline="black")
    draw.rectangle((650,260,1150,420), outline="black")

    draw.text((60,270),"Bill To",font=bold,fill="black")
    draw.text((60,300),random.choice(names),font=text,fill="black")

    draw.text((660,270),"Invoice Details",font=bold,fill="black")
    draw.text((660,300),"Inv No: "+str(random.randint(1000,9999)),font=text,fill="black")

    # table
    y = 450
    cols = [50, 250, 400, 550, 700, 850, 1000]
    headers = ["Sr","Item","HSN","Qty","Rate","GST","Total"]

    for i in range(len(headers)):
        draw.text((cols[i], y), headers[i], font=bold, fill="black")

    draw.line((50,y+30,1150,y+30), fill="black", width=2)
    y += 50

    total = 0

    for i in range(6):
        qty = random.randint(1,10)
        rate = random.randint(100,500)
        amt = qty * rate
        tax = amt * 0.18
        final = amt + tax
        total += final

        row = [
            str(i+1),
            random.choice(items),
            str(random.randint(1000,9999)),
            str(qty),
            str(rate),
            "18%",
            f"{final:.2f}"
        ]

        for j in range(len(row)):
            draw.text((cols[j], y), row[j], font=text, fill="black")

        draw.line((50,y+30,1150,y+30), fill="gray")
        y += 40

    draw.rectangle((50,440,1150,y), outline="black")

    # summary
    draw.rectangle((700,y+20,1150,y+200), outline="black")
    draw.text((720,y+40),"TOTAL: "+str(round(total,2)), font=bold, fill="black")

    draw.text((50,y+40),"Bank: SBI", font=text, fill="black")
    draw.text((50,y+80),"IFSC: SBIN0001234", font=text, fill="black")

    draw.text((50,y+200),"Authorized Signature", font=text, fill="black")

    img.save(os.path.join(output_dir, f"invoice_{idx}.png"))



count = 0

# 70 advanced
for v in range(5):
    for i in range(14):   # 5*14 = 70
        advanced_invoice(count, v)
        count += 1

# 30 industrial
for i in range(30):
    industrial_invoice(count)
    count += 1

print("✅ FINAL 100 MIXED INVOICES GENERATED")