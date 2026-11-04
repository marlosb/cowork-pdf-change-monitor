# Generates v1.pdf, v1b.pdf (same content, new date) and v2.pdf (6 planted changes) for testing.
# Requires: pip install reportlab
import random, sys
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
random.seed(7)
W="instruction operator must verify the account balance before submitting the monthly declaration form within business days according to rule".split()
paras={}
secs=[]
for ch in range(1,31):
    for sub in range(1,9):
        key=f"{ch}.{sub}"
        secs.append(key)
        paras[key]=[" ".join(random.choice(W) for _ in range(60)).capitalize()+"." for _ in range(6)]
def build(path, ver, mutate):
    p=dict((k,list(v)) for k,v in paras.items()); titles={k:f"{k} Procedure topic {k}" for k in secs}; order=list(secs)
    if mutate:
        p["2.3"][1]=p["2.3"][1].replace("monthly","quarterly",1)
        p["1.2"].insert(2,"New requirement: all submissions must include the digital signature certificate issued after January 2026.")
        p["10.4"][3]="The deadline for filing is now 15 business days instead of 10 business days."
        order.remove("15.6")
        order.insert(order.index("22.1")+1,"22.1A"); titles["22.1A"]="22.1.1 Additional verification for foreign accounts"
        p["22.1A"]=["Foreign accounts require an additional verification step with the compliance team."]
        titles["7.7"]="7.7 Procedure topic renamed 7.7"
        p["12.2"][0]=p["12.2"][0].upper().replace(" ","  ")  # cosmetic only? case change
    ss=getSampleStyleSheet(); story=[]
    for k in order:
        story.append(Paragraph(titles[k], ss["Heading2"]))
        for t in p[k]: story.append(Paragraph(t, ss["BodyText"]))
    def hf(c,d):
        c.setFont("Helvetica",8); c.drawString(40,815,f"Instruction Manual - Revised: {ver}"); c.drawString(280,20,f"Page {d.page}")
    SimpleDocTemplate(path,pagesize=A4,title=ver).build(story,onFirstPage=hf,onLaterPages=hf)
import os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples"))
build("v1.pdf","01/10/2026",False); build("v1b.pdf","01/11/2026",False); build("v2.pdf","01/11/2026",True)
