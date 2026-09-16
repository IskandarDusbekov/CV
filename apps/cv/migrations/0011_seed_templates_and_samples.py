from django.db import migrations

TEMPLATE_ORDER = [
    # (kod, pro)
    ("ats_modern", False), ("simple", False), ("classic", False), ("ats", False), ("minimal", False),
    ("teal", True), ("bold", True), ("modern", True), ("creative", True), ("executive", True), ("elegant", True), ("dark", True),
]

PHONE = "+998 90 123 45 67"


def _cv(name, title, email, location, summary, skills, languages, experience, education, projects=None):
    return {
        "_language": "uz", "full_name": name, "job_title": title, "email": email, "phone": PHONE, "location": location,
        "github": "", "linkedin": "", "summary": summary, "skills": skills, "languages": languages,
        "experience": experience, "education": education, "projects": projects or [],
    }


SAMPLES = [
    {
        "slug": "sotuvchi-konsultant", "profession": "Sotuvchi-konsultant", "category": "Savdo", "template": "simple",
        "seo_title": "Sotuvchi-konsultant rezyume namunasi — tayyor, bepul",
        "seo_description": "Sotuvchi-konsultant uchun tayyor rezyume namunasi: tajriba, ko'nikmalar va yutuqlar qanday yoziladi. Ismingizni yozib 2 daqiqada o'zingiznikini yarating.",
        "intro": "Sotuvchi rezyumesida eng muhimi — natija. «Sotuv bilan shug'ullandim» o'rniga reja necha foizga bajarilgani, kuniga nechta mijozga xizmat ko'rsatganingizni yozing.\n\n"
                 "Kassa apparati, 1C, mahsulot joylashtirish (merchandayzing) va rus tilini bilish savdoda ko'p so'raladi — bor bo'lsa, albatta qo'shing.\n\n"
                 "Tajribangiz yo'q bo'lsa, oilaviy do'konda yordam berganingiz yoki xushmuomalaligingizni misol bilan yozing.",
        "cv": _cv("Dilshod Rahimov", "Sotuvchi-konsultant", "dilshod.rahimov@gmail.com", "Toshkent",
                  "3 yillik savdo tajribasiga ega sotuvchi-konsultant. Mijozga ehtiyojini aniqlab, mos mahsulotni tavsiya qilishni yaxshi bilaman. "
                  "Oylik sotuv rejasini muntazam oshirib bajaraman.",
                  ["Mijozlar bilan muloqot", "Sotuv texnikalari", "Kassa apparati", "1C: Savdo", "Merchandayzing", "E'tirozlar bilan ishlash"],
                  ["O'zbek — ona tili", "Rus — o'rta (B1)"],
                  [{"position": "Sotuvchi-konsultant", "company": "Texnomart", "duration": "2023 — hozir",
                    "responsibilities": ["Kuniga 40+ mijozga maishiy texnika bo'yicha maslahat beraman",
                                         "Oylik sotuv rejasini 6 oy ketma-ket 110%+ bajardim",
                                         "Muddatli to'lov (rassrochka) shartnomalarini rasmiylashtiraman"]},
                   {"position": "Sotuvchi", "company": "Korzinka", "duration": "2021 — 2023",
                    "responsibilities": ["Kassada ishlash va kunlik hisobotni topshirish",
                                         "Mahsulotlarni tokchalarga joylashtirish va muddatini nazorat qilish"]}],
                  [{"institution": "Toshkent moliya kolleji", "degree": "Buxgalteriya hisobi", "year": "2018 — 2021"}]),
    },
    {
        "slug": "kassir", "profession": "Kassir", "category": "Savdo", "template": "ats_modern",
        "seo_title": "Kassir rezyume namunasi — tajribali va tajribasiz",
        "seo_description": "Kassir uchun tayyor rezyume namunasi. Pul bilan ishlash, kassa dasturlari va mas'uliyatni qanday yozish kerak — misol bilan. Bepul yarating.",
        "intro": "Kassir rezyumesida ish beruvchi ishonchlilik va aniqlikni izlaydi: «kamomadsiz ishladim», «kuniga 300+ xarid» kabi raqamlar sizni ajratib turadi.\n\n"
                 "Qaysi kassa dasturlari (1C, iiko, R-Keeper) va terminallar bilan ishlaganingizni aniq yozing.\n\n"
                 "Smenali ishlashga tayyor bo'lsangiz, buni ham qo'shing — bu savdo va supermarketlar uchun muhim.",
        "cv": _cv("Malika Tursunova", "Kassir", "malika.tursunova@mail.ru", "Samarqand",
                  "Supermarketda 2 yil kassir bo'lib ishlaganman. Naqd va karta to'lovlari bilan aniq ishlayman, kamomadsiz smena topshiraman. Smenali ish grafigiga tayyorman.",
                  ["Naqd va karta to'lovlari", "1C: Kassa", "POS terminal", "Kunlik hisobot", "Xushmuomalalik", "Diqqatlilik"],
                  ["O'zbek — ona tili", "Rus — boshlang'ich (A2)"],
                  [{"position": "Kassir", "company": "Makro supermarketi", "duration": "2022 — hozir",
                    "responsibilities": ["Kuniga 300+ xaridni rasmiylashtiraman", "2 yil davomida birorta kamomadsiz smena topshirdim",
                                         "Yangi kassirlarga ish tartibini o'rgataman"]}],
                  [{"institution": "Samarqand 12-maktab", "degree": "Umumiy o'rta ta'lim", "year": "2021"}]),
    },
    {
        "slug": "call-markaz-operatori", "profession": "Call-markaz operatori", "category": "Xizmat ko'rsatish", "template": "ats_modern",
        "seo_title": "Call-markaz operatori rezyume namunasi",
        "seo_description": "Operator (call-center) uchun tayyor rezyume namunasi: qo'ng'iroqlar soni, CRM va muloqot ko'nikmalari qanday yoziladi. 2 daqiqada o'zingiznikini yarating.",
        "intro": "Operator rezyumesida kuniga nechta qo'ng'iroq qabul qilganingiz va mijoz shikoyatlarini qanday hal qilganingizni yozing.\n\n"
                 "Bir nechta tilda gaplasha olish (o'zbek, rus, ingliz) call-markazlarda katta ustunlik — til darajasini aniq ko'rsating.\n\n"
                 "CRM tizimlari (Bitrix24, amoCRM) va kompyuterda tez yozish ko'nikmasini qo'shishni unutmang.",
        "cv": _cv("Shahnoza Karimova", "Call-markaz operatori", "shahnoza.k@gmail.com", "Toshkent",
                  "Mijozlar bilan muloqotda 2 yillik tajribaga ega operator. Kiruvchi va chiquvchi qo'ng'iroqlar, shikoyatlarni hal qilish va CRM bilan ishlashni bilaman.",
                  ["Telefon orqali muloqot", "Bitrix24", "amoCRM", "Shikoyatlarni hal qilish", "Tez yozish", "Stressga chidamlilik"],
                  ["O'zbek — ona tili", "Rus — erkin (C1)", "Ingliz — o'rta (B1)"],
                  [{"position": "Operator", "company": "Uzum Market qo'llab-quvvatlash markazi", "duration": "2023 — hozir",
                    "responsibilities": ["Kuniga 80–100 ta kiruvchi qo'ng'iroqqa javob beraman", "Mijozlar mamnunligi bahosi — 4,8/5",
                                         "Buyurtma muammolarini birinchi qo'ng'iroqda hal qilaman"]}],
                  [{"institution": "O'zbekiston davlat jahon tillari universiteti", "degree": "Rus filologiyasi, 3-kurs", "year": "2022 — hozir"}]),
    },
    {
        "slug": "smm-menejer", "profession": "SMM menejer", "category": "Marketing", "template": "classic",
        "seo_title": "SMM menejer rezyume namunasi — portfolio bilan",
        "seo_description": "SMM mutaxassis uchun tayyor rezyume namunasi: natijalar, reklama, kontent va portfolio qanday ko'rsatiladi. Bepul shablon va 2 daqiqada tayyor.",
        "intro": "SMM rezyumesida obunachilar o'sishi, qamrov va reklamadan kelgan sotuvlar kabi raqamlar eng kuchli dalil.\n\n"
                 "Qaysi sahifalarni yuritganingizga havola (portfolio) qo'shing — HR buni albatta ochib ko'radi.\n\n"
                 "Canva, CapCut, Meta Ads, Telegram Ads kabi vositalarni alohida ko'nikmalar qatorida yozing.",
        "cv": _cv("Dilnoza Aliyeva", "SMM menejer", "dilnoza.aliyeva@gmail.com", "Toshkent",
                  "Brendlar uchun Instagram va Telegram sahifalarini 3 yildan beri yurituvchi SMM menejer. Kontent reja, dizayn va reklamani o'zim qilaman, natijani raqamlarda o'lchayman.",
                  ["Kontent reja", "Meta Ads", "Telegram Ads", "Canva", "CapCut", "Kopirayting", "Analitika"],
                  ["O'zbek — ona tili", "Rus — erkin (C1)", "Ingliz — o'rta (B2)"],
                  [{"position": "SMM menejer", "company": "Ofis mebel do'koni", "duration": "2023 — hozir",
                    "responsibilities": ["Instagram sahifani 6 oyda 2 000 dan 15 000 obunachiga yetkazdim",
                                         "Meta Ads orqali oyiga 120+ so'rov olib keldim, bitta so'rov narxi 30% arzonladi",
                                         "Haftasiga 5 ta Reels va 10 ta stories tayyorlayman"]},
                   {"position": "SMM (frilans)", "company": "Kichik bizneslar", "duration": "2021 — 2023",
                    "responsibilities": ["5 ta mijoz sahifasini yuritdim: kafe, go'zallik saloni, o'quv markazi"]}],
                  [{"institution": "TDIU", "degree": "Marketing, bakalavr", "year": "2018 — 2022"}]),
    },
    {
        "slug": "buxgalter", "profession": "Buxgalter", "category": "Moliya", "template": "classic",
        "seo_title": "Buxgalter rezyume namunasi — 1C va soliq hisoboti",
        "seo_description": "Buxgalter uchun tayyor rezyume namunasi: 1C, soliq hisobotlari, my.soliq va birlamchi hujjatlar bilan ishlash qanday yoziladi. Bepul yarating.",
        "intro": "Buxgalter rezyumesida qaysi hisobotlarni mustaqil topshirganingiz va qanday dasturlar bilan ishlaganingiz asosiy o'rinda turadi.\n\n"
                 "Kompaniya hajmini ko'rsating: nechta xodimga oylik hisoblagansiz, qanday soliq rejimi bo'lgan.\n\n"
                 "Malaka oshirish kurslari va sertifikatlar (masalan, 1C sertifikati) bo'lsa, «Ta'lim» bo'limiga qo'shing.",
        "cv": _cv("Nodira Yusupova", "Buxgalter", "nodira.yusupova@mail.ru", "Toshkent",
                  "Savdo va xizmat ko'rsatish kompaniyalarida 5 yillik tajribaga ega buxgalter. Birlamchi hujjatlardan tortib soliq hisobotlarigacha mustaqil yuritaman.",
                  ["1C: Buxgalteriya", "Soliq hisobotlari", "my.soliq.uz", "Ish haqi hisoblash", "Excel", "Birlamchi hujjatlar"],
                  ["O'zbek — ona tili", "Rus — erkin (C1)"],
                  [{"position": "Buxgalter", "company": "\"Grand Savdo\" MChJ", "duration": "2021 — hozir",
                    "responsibilities": ["Oylik va choraklik soliq hisobotlarini o'z vaqtida topshiraman",
                                         "45 nafar xodimga ish haqi va ushlanmalarni hisoblayman",
                                         "Kontragentlar bilan solishtirma dalolatnomalarni yuritaman"]},
                   {"position": "Buxgalter yordamchisi", "company": "Audit firmasi", "duration": "2019 — 2021",
                    "responsibilities": ["Birlamchi hujjatlarni 1C ga kiritish", "Bank ko'chirmalarini tekshirish"]}],
                  [{"institution": "TDIU", "degree": "Buxgalteriya hisobi va audit, bakalavr", "year": "2015 — 2019"}]),
    },
    {
        "slug": "python-dasturchi", "profession": "Junior Python dasturchi", "category": "IT", "template": "ats",
        "seo_title": "Junior dasturchi rezyume namunasi — tajribasiz IT",
        "seo_description": "Junior Python dasturchi uchun tayyor rezyume namunasi: loyihalar, GitHub va ko'nikmalar qanday yoziladi. ATS'dan o'tadigan shablon, bepul.",
        "intro": "Junior dasturchida ish tajribasi kam bo'lishi normal — o'rniga loyihalar va GitHub havolasini ko'rsating.\n\n"
                 "Har bir loyihada nima qilganingiz va qaysi texnologiyalarni ishlatganingizni 1–2 gapda yozing.\n\n"
                 "IT kompaniyalar ko'pincha ATS dasturidan foydalanadi, shuning uchun oddiy, bir ustunli (ATS) shablon tanlang.",
        "cv": _cv("Jasur Nematov", "Junior Python dasturchi", "jasur.nematov@gmail.com", "Toshkent",
                  "Python va Django bo'yicha o'quv kursi va 3 ta shaxsiy loyihaga ega junior dasturchi. REST API yozish, ma'lumotlar bazasi bilan ishlash va jamoada Git orqali ishlashni bilaman.",
                  ["Python", "Django", "Django REST Framework", "PostgreSQL", "Git", "HTML/CSS", "Linux asoslari"],
                  ["O'zbek — ona tili", "Ingliz — texnik matnlarni o'qiyman (B1)", "Rus — o'rta (B1)"],
                  [{"position": "Backend stajyor", "company": "IT Park rezidenti — startap", "duration": "2024 — 3 oy",
                    "responsibilities": ["Buyurtmalar uchun 8 ta REST API endpoint yozdim", "Unit testlar bilan kod qamrovini 60% ga yetkazdim"]}],
                  [{"institution": "TATU", "degree": "Dasturiy injiniring, 4-kurs", "year": "2021 — hozir"},
                   {"institution": "Najot Ta'lim", "degree": "Python Backend kursi (sertifikat)", "year": "2023"}],
                  [{"title": "Onlayn kutubxona", "description": "Kitob qidirish, ijaraga olish va Telegram orqali eslatma yuboradigan veb-ilova.",
                    "technologies": ["Django", "PostgreSQL", "aiogram"]},
                   {"title": "Valyuta kursi boti", "description": "Markaziy bank kurslarini har kuni yuboradigan Telegram bot.",
                    "technologies": ["Python", "aiogram", "Redis"]}]),
    },
    {
        "slug": "ingliz-tili-oqituvchisi", "profession": "Ingliz tili o'qituvchisi", "category": "Ta'lim", "template": "minimal",
        "seo_title": "O'qituvchi rezyume namunasi — ingliz tili",
        "seo_description": "Ingliz tili o'qituvchisi uchun tayyor rezyume namunasi: IELTS natijalari, o'quvchilar yutuqlari va metodikalar qanday yoziladi. Bepul.",
        "intro": "O'qituvchi rezyumesida o'quvchilaringiz natijasi eng kuchli dalil: «30 nafar o'quvchi IELTS 6.5+ oldi».\n\n"
                 "O'zingizning sertifikatlaringizni (IELTS, CEFR, CELTA, TKT) aniq ball va yili bilan yozing.\n\n"
                 "Qaysi yosh guruhlar va qaysi darajalar bilan ishlaganingizni ko'rsating — o'quv markazlari buni so'raydi.",
        "cv": _cv("Kamola Ismoilova", "Ingliz tili o'qituvchisi", "kamola.ismoilova@gmail.com", "Namangan",
                  "IELTS 8.0 sertifikatiga ega, 4 yillik tajribali ingliz tili o'qituvchisi. Kattalar va o'smirlar guruhlarini IELTS va umumiy ingliz tiliga tayyorlayman.",
                  ["IELTS tayyorlov", "Communicative approach", "Guruh boshqaruvi", "Google Classroom", "Kahoot", "Test tuzish"],
                  ["O'zbek — ona tili", "Ingliz — IELTS 8.0 (C1)", "Rus — o'rta (B1)"],
                  [{"position": "Ingliz tili o'qituvchisi", "company": "\"Cambridge\" o'quv markazi", "duration": "2022 — hozir",
                    "responsibilities": ["Bir vaqtda 6 ta guruhga (70+ o'quvchi) dars beraman",
                                         "2 yilda 35 nafar o'quvchim IELTS 6.5 va undan yuqori ball oldi",
                                         "Markaz uchun mock-test tizimini ishlab chiqdim"]},
                   {"position": "Ingliz tili o'qituvchisi", "company": "Namangan 21-maktab", "duration": "2020 — 2022",
                    "responsibilities": ["5–9-sinflarga dars berdim", "Tuman olimpiadasiga 4 nafar sovrindor tayyorladim"]}],
                  [{"institution": "Namangan davlat universiteti", "degree": "Ingliz tili va adabiyoti, bakalavr", "year": "2016 — 2020"}]),
    },
    {
        "slug": "haydovchi", "profession": "Haydovchi", "category": "Transport", "template": "simple",
        "seo_title": "Haydovchi rezyume namunasi — B, C toifa",
        "seo_description": "Haydovchi va kuryer uchun tayyor rezyume namunasi: guvohnoma toifasi, avariyasiz staj va shahar bilimini qanday yozish kerak. Bepul yarating.",
        "intro": "Haydovchi rezyumesida birinchi navbatda guvohnoma toifasi (B, C, D, E) va haydovchilik staji yoziladi.\n\n"
                 "«Avariyasiz 8 yil», «shaharni yaxshi bilaman», «shaxsiy avtomobilim bor» — ish beruvchi aynan shularni izlaydi.\n\n"
                 "Yuk tashish, kuryerlik yoki taksi xizmatidagi tajribangizni kompaniya nomi bilan ko'rsating.",
        "cv": _cv("Bobur Xolmatov", "Haydovchi (B, C toifa)", "bobur.xolmatov@mail.ru", "Toshkent",
                  "10 yillik haydovchilik stajiga ega, avariyasiz ishlagan haydovchi. Toshkent shahri va viloyat yo'llarini yaxshi bilaman, yuklarni o'z vaqtida va xavfsiz yetkazaman.",
                  ["B va C toifali guvohnoma", "Avariyasiz 10 yil", "Shahar va viloyat yo'llari", "Avtomobil texnik nazorati", "Yuk hujjatlari", "Intizomlilik"],
                  ["O'zbek — ona tili", "Rus — o'rta (B1)"],
                  [{"position": "Yuk mashinasi haydovchisi", "company": "\"Asl Logistika\" MChJ", "duration": "2020 — hozir",
                    "responsibilities": ["Do'konlarga kuniga 12–15 manzilga mahsulot yetkazaman", "Yo'l varaqalari va yuk hujjatlarini yuritaman",
                                         "Mashinaning texnik holatini nazorat qilaman"]},
                   {"position": "Haydovchi-kuryer", "company": "Express24", "duration": "2017 — 2020",
                    "responsibilities": ["Kuniga 25+ buyurtmani o'z vaqtida yetkazdim"]}],
                  [{"institution": "Toshkent avtotransport kolleji", "degree": "Avtomobillarga texnik xizmat ko'rsatish", "year": "2011 — 2014"}]),
    },
    {
        "slug": "talaba-tajribasiz", "profession": "Talaba (tajribasiz)", "category": "Tajribasiz", "template": "ats_modern",
        "seo_title": "Tajribasiz rezyume namunasi — talaba va bitiruvchilar",
        "seo_description": "Ish tajribasi yo'q talaba va bitiruvchilar uchun tayyor rezyume namunasi: ta'lim, amaliyot, volontyorlik va ko'nikmalar bilan. Bepul yarating.",
        "intro": "Tajribasiz rezyumeni «Ta'lim», «Ko'nikmalar» va «Loyihalar» bilan boshlang — bu mutlaqo normal.\n\n"
                 "Amaliyot, volontyorlik, kurs ishlari, olimpiada va tanlovlar — bularning hammasi tajriba hisoblanadi.\n\n"
                 "Qaysi kunlari va soatlarda ishlay olishingizni yozing: talabalarni ko'pincha yarim stavka yoki smenali ishga olishadi.",
        "cv": _cv("Aziza Sobirova", "Stajyor / yordamchi xodim", "aziza.sobirova@gmail.com", "Toshkent",
                  "Iqtisodiyot yo'nalishi 3-kurs talabasi. Tez o'rganaman, jamoada ishlashni yaxshi ko'raman va Excel bilan ishlashni bilaman. Haftasiga 20 soatgacha ishlay olaman.",
                  ["MS Excel", "MS Word, PowerPoint", "Google Sheets", "Jamoada ishlash", "Taqdimot qilish", "Vaqtni boshqarish"],
                  ["O'zbek — ona tili", "Ingliz — IELTS 6.0", "Rus — o'rta (B1)"],
                  [{"position": "Volontyor", "company": "\"Yoshlar forumi — 2024\"", "duration": "2024",
                    "responsibilities": ["300+ ishtirokchini ro'yxatdan o'tkazish va yo'naltirishda yordam berdim"]},
                   {"position": "Amaliyotchi", "company": "Tijorat banki filiali", "duration": "2024 — 1 oy",
                    "responsibilities": ["Mijozlar arizalarini ro'yxatga oldim va hujjatlarni tartibga soldim"]}],
                  [{"institution": "TDIU", "degree": "Iqtisodiyot, 3-kurs (2026-yilda tugatadi)", "year": "2023 — hozir"}],
                  [{"title": "Kurs ishi: kichik biznesda moliyaviy tahlil", "description": "Oilaviy do'konning 1 yillik savdosini Excel'da tahlil qilib, xarajatlarni 12% kamaytirish taklifini berdim.",
                    "technologies": ["Excel"]}]),
    },
    {
        "slug": "ofis-menejeri", "profession": "Ofis menejeri", "category": "Administrativ", "template": "classic",
        "seo_title": "Ofis menejeri rezyume namunasi — administrator",
        "seo_description": "Ofis menejeri va administrator uchun tayyor rezyume namunasi: hujjat aylanishi, uchrashuvlar va ofis ta'minoti qanday yoziladi. Bepul.",
        "intro": "Ofis menejeri rezyumesida tartib va tashkilotchilik ko'nikmalarini aniq ishlar orqali ko'rsating.\n\n"
                 "Hujjat aylanishi, rahbar jadvalini yuritish, xaridlar va xodimlarni qabul qilish kabi vazifalarni yozing.\n\n"
                 "Kompyuter dasturlari (Word, Excel, Google Workspace) va tillarni bilish bu lavozimda majburiy talab hisoblanadi.",
        "cv": _cv("Gulnora Ahmedova", "Ofis menejeri", "gulnora.ahmedova@gmail.com", "Toshkent",
                  "Ofis ishlarini tashkil qilishda 4 yillik tajribaga ega. Hujjat aylanishi, rahbar jadvali, xaridlar va mehmonlarni kutib olishni mustaqil yuritaman.",
                  ["Hujjat aylanishi", "Rahbar jadvalini yuritish", "MS Office", "Google Workspace", "Xaridlar", "Ish yozishmalari"],
                  ["O'zbek — ona tili", "Rus — erkin (C1)", "Ingliz — o'rta (B1)"],
                  [{"position": "Ofis menejeri", "company": "Qurilish kompaniyasi", "duration": "2022 — hozir",
                    "responsibilities": ["60 nafar xodimli ofisning kundalik ishlarini tashkil qilaman",
                                         "Kanselyariya va xo'jalik xaridlarini optimallashtirib, xarajatni 15% kamaytirdim",
                                         "Rahbar uchrashuvlari va xizmat safarlarini rejalashtiraman"]},
                   {"position": "Administrator", "company": "Xususiy klinika", "duration": "2020 — 2022",
                    "responsibilities": ["Bemorlarni qabul qilish va shifokorlar jadvalini yuritish"]}],
                  [{"institution": "O'zbekiston milliy universiteti", "degree": "Menejment, bakalavr", "year": "2016 — 2020"}]),
    },
]


def seed(apps, schema_editor):
    TemplateSetting = apps.get_model("cv", "TemplateSetting")
    ResumeSample = apps.get_model("cv", "ResumeSample")
    for i, (code, pro) in enumerate(TEMPLATE_ORDER):
        TemplateSetting.objects.get_or_create(code=code, defaults={"is_pro": pro, "sort_order": i * 10})
    for i, s in enumerate(SAMPLES):
        ResumeSample.objects.get_or_create(slug=s["slug"], defaults={
            "profession": s["profession"], "category": s["category"], "seo_title": s["seo_title"],
            "seo_description": s["seo_description"], "intro": s["intro"], "cv_json": s["cv"],
            "template_code": s["template"], "sort_order": i * 10,
        })


class Migration(migrations.Migration):

    dependencies = [("cv", "0010_resumesample_templatesetting_cv_free_pdf_and_more")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
