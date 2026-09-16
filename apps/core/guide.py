"""«Qo'llanma» sahifasi: ish qidiruvchilarning eng ko'p beradigan savollari.

Javoblar ishonchli HTML (faqat shu fayldan keladi, foydalanuvchi kiritmaydi).
Matnni o'zgartirish uchun shu faylni tahrirlang — sahifa va Google uchun FAQ belgilash o'zi yangilanadi.
"""

SECTIONS = [
    {
        "id": "boshlash",
        "icon": "🧭",
        "title": "Rezyume asoslari",
        "items": [
            ("Rezyume nima va u nima uchun kerak?",
             "<p>Rezyume — sizning ish bo'yicha qisqa «tanishtiruvchi varag'ingiz»: kimsiz, nima qila olasiz, qayerda ishlagansiz va o'qigansiz. "
             "HR (kadrlar bo'limi) har bir vakansiyaga o'nlab ariza oladi va har biriga o'rtacha <b>6–10 soniya</b> qaraydi. "
             "Yaxshi rezyume sizni suhbatga chaqirishlari uchun kerak — ishni suhbatda olasiz.</p>"),
            ("CV va rezyume farqi bormi?",
             "<p>O'zbekistonda ikkalasi bir xil ma'noda ishlatiladi. Aslida CV (Curriculum Vitae) — ilmiy va akademik ishlar uchun uzunroq hujjat, "
             "rezyume esa qisqa (1–2 bet) va aniq ishga moslangan bo'ladi. Vakansiyada «CV yuboring» deyilsa ham, oddiy rezyumeni yuborsangiz bo'ladi.</p>"),
            ("Rezyume necha bet bo'lishi kerak?",
             "<ul><li><b>1 bet</b> — tajribasi 5 yilgacha bo'lganlar, talabalar va yangi boshlovchilar uchun.</li>"
             "<li><b>2 bet</b> — tajribasi ko'p, rahbarlik lavozimlarida ishlaganlar uchun.</li>"
             "<li>3 betdan oshmasin: HR baribir hammasini o'qimaydi.</li></ul>"),
            ("Rezyumega rasm qo'yish kerakmi?",
             "<p>Majburiy emas. O'zbekiston va MDH kompaniyalarida rasm odatiy hol, xalqaro kompaniyalar va xorijga topshirishda esa ko'pincha <b>rasmsiz</b> yuboriladi. "
             "Qo'ysangiz — oq yoki bir xil fonda, yuzingiz aniq ko'rinadigan, jiddiy rasm bo'lsin. Selfi, filtrli yoki to'y rasmlari yaramaydi.</p>"),
            ("Qaysi tilda yozish kerak?",
             "<p>Vakansiya qaysi tilda yozilgan bo'lsa, rezyume ham shu tilda bo'lgani yaxshi. Xalqaro kompaniya va IT uchun — ingliz tili, "
             "ko'p mahalliy kompaniyalar uchun — o'zbek yoki rus tili. tezrezyume.uz'da bitta ma'lumotdan uch tilda rezyume qilish mumkin.</p>"),
            ("PDF yoki Word — qaysi birini yuboray?",
             "<p>Odatda <b>PDF</b> yuboring: har qanday telefon va kompyuterda bir xil ko'rinadi, dizayn buzilmaydi. "
             "Word (.docx) faqat kompaniya so'rasa yoki rezyumeni o'zingiz tahrirlamoqchi bo'lsangiz kerak.</p>"),
            ("Fayl nomini qanday qo'yay?",
             "<p>«rezyume_final_2.pdf» emas, balki <b>Ism_Familiya_Lavozim.pdf</b>, masalan <code>Dilnoza_Karimova_SMM.pdf</code>. "
             "HR yuzlab fayl orasidan sizni tez topadi.</p>"),
        ],
    },
    {
        "id": "tajribasiz",
        "icon": "🌱",
        "title": "Ish tajribam yo'q",
        "items": [
            ("Hech qayerda ishlamaganman. Rezyumega nima yozaman?",
             "<p>Tajriba faqat rasmiy ish emas. Quyidagilarning hammasi hisoblanadi:</p>"
             "<ul><li><b>Amaliyot</b> (praktika) — o'qish davomidagi ham.</li>"
             "<li><b>Volontyorlik</b> — tadbirlar, xayriya, maktab yoki mahalla ishlari.</li>"
             "<li><b>O'quv loyihalari</b> — kurs ishi, diplom ishi, jamoaviy loyiha.</li>"
             "<li><b>Oilaviy biznesda yordam</b> — do'konda sotuvchilik, hisob-kitob, mijozlar bilan ishlash.</li>"
             "<li><b>Frilans va shaxsiy ishlar</b> — Instagram sahifa yuritish, dizayn qilib berish, repetitorlik.</li>"
             "<li><b>Kurslar va sertifikatlar</b> — IT, til, buxgalteriya, Excel.</li>"
             "<li><b>Tanlov va olimpiadalar</b>, sport yutuqlari, faol ishtirok.</li></ul>"
             "<p>Rezyumeni «Ish tajribasi» emas, <b>«Ta'lim», «Ko'nikmalar» va «Loyihalar»</b> bo'limlaridan boshlang.</p>"),
            ("Talabaman. Ishga olishadimi?",
             "<p>Ha. Ko'p kompaniyalar talabalarni <b>stajyor (intern), yarim stavka yoki smenali</b> ishlarga oladi: savdo, call-markaz, SMM, kafe, IT stajirovka. "
             "Rezyumeda qaysi kursda o'qishingiz, o'qish qachon tugashi va <b>qaysi kunlari/soatlarda ishlay olishingizni</b> yozing — bu HR uchun muhim.</p>"),
            ("Maktabni endi bitirdim, diplomim ham, tajribam ham yo'q. Qayerdan boshlay?",
             "<ul><li>Tajriba talab qilinmaydigan ishlardan boshlang: sotuvchi-konsultant, kassir, operator, ofitsiant, kuryer, omborchi, administrator yordamchisi.</li>"
             "<li>Rezyumeda <b>shaxsiy sifatlar</b>ni misol bilan yozing: «vaqtida kelaman» emas, «11 yil maktabni sababsiz qoldirmadim».</li>"
             "<li>Qisqa bepul yoki arzon kurs o'ting (kompyuter savodxonligi, Excel, til) — rezyumeda katta farq qiladi.</li>"
             "<li>«Tajribasiz, lekin o'rganishga tayyorman» degan ochiq xabar bilan yuboring — bu yaxshi qabul qilinadi.</li></ul>"),
            ("Tajribam yo'qligini yashirishim kerakmi?",
             "<p>Yo'q. Yolg'on tajriba yozmang — suhbatda yoki sinov muddatida albatta bilinadi va ishonch yo'qoladi. "
             "Buning o'rniga borini to'g'ri ko'rsating: nimalarni bilasiz, nimani o'rgangansiz, qanday natija ko'rsatgansiz. "
             "tezrezyume.uz ham siz yozmagan ish joyi, sana yoki diplomni <b>o'ylab topmaydi</b>.</p>"),
            ("Ishlamagan davrim (tanaffus) bor. Qanday tushuntiraman?",
             "<p>Bu odatiy hol: harbiy xizmat, farzand parvarishi, o'qish, kasallik, ko'chish, oila ishlari. "
             "Rezyumeda qisqa yozish yetarli, masalan: <i>«2022–2023 — farzand parvarishi»</i> yoki <i>«2023 — IT kurslarida o'qish»</i>. "
             "Suhbatda sababni xotirjam, 1–2 gapda ayting va shu davrda nimani o'rganganingizni qo'shing.</p>"),
            ("Harbiy xizmatni rezyumega yozish kerakmi?",
             "<p>Ha, ayniqsa ish tajribangiz kam bo'lsa. Intizom, mas'uliyat, jamoada ishlash — ish beruvchi qadrlaydigan sifatlar. "
             "Vazifangiz (haydovchi, aloqachi va h.k.) bo'lsa, uni ham yozing.</p>"),
        ],
    },
    {
        "id": "diplom",
        "icon": "🎓",
        "title": "Diplom va ta'lim",
        "items": [
            ("Diplomsiz ish topsa bo'ladimi?",
             "<p>Ha, ko'p sohalarda bo'ladi. Savdo, xizmat ko'rsatish, call-markaz, logistika, SMM, dizayn, dasturlash, "
             "qurilish va ko'plab ishchi kasblarda asosiy narsa — <b>ko'nikma va natija</b>. "
             "IT va dizaynda diplomdan ko'ra <b>portfolio</b> (qilgan ishlaringiz) muhimroq.</p>"),
            ("Qaysi ishlarga diplom albatta kerak?",
             "<p>Qonun yoki kasb talabi bilan malaka hujjati talab qilinadigan ishlar: <b>shifokor va hamshira, o'qituvchi, huquqshunos, farmatsevt, "
             "davlat xizmatining ko'p lavozimlari</b>, ba'zi muhandislik va moliya lavozimlari. "
             "Aniq talab vakansiyaning o'zida yoziladi — «oliy ma'lumot shart» deyilganini diqqat bilan o'qing.</p>"),
            ("Diplomim yo'q. Uning o'rniga nimani ko'rsataman?",
             "<ul><li><b>Sertifikatlar</b> — o'quv markazi, onlayn kurslar (Coursera, IT Park, Najot Ta'lim va boshqalar).</li>"
             "<li><b>Portfolio</b> — dizaynlar, saytlar, Instagram sahifalar, fotosuratlar havolasi.</li>"
             "<li><b>Natijalar raqam bilan</b> — «oyiga 120 ta mijozga xizmat ko'rsatdim».</li>"
             "<li><b>Tavsiya</b> — oldingi ish beruvchi yoki ustozingiz raqami (so'ralsa).</li></ul>"),
            ("O'qishni tugatmaganman yoki hozir o'qiyapman. Qanday yozaman?",
             "<p>Yolg'on «bitirganman» demang. To'g'ri variantlar:</p>"
             "<ul><li><i>TDIU, Iqtisodiyot — 3-kurs talabasi (2026-yilda tugatadi)</i></li>"
             "<li><i>TATU, Dasturiy injiniring — 2 kurs o'qigan (2019–2021)</i></li></ul>"),
            ("Kollej/texnikum yoki litsey diplomi hisoblanadimi?",
             "<p>Ha — bu o'rta maxsus yoki professional ta'lim. «Ta'lim» bo'limiga o'quv joyi, yo'nalish va bitirgan yilni yozing. "
             "Ko'p ishchi kasblar (elektrik, payvandchi, tikuvchi, oshpaz, hamshira yordamchisi) uchun aynan shu hujjat so'raladi.</p>"),
            ("Diplom va sertifikat nusxalarini rezyumega qo'shaymi?",
             "<p>Yo'q, rezyumega faqat nomini yozasiz. Nusxalarni kompaniya <b>so'raganda</b> yoki ishga qabul qilishda alohida topshirasiz.</p>"),
            ("Til bilish darajasini qanday yozaman?",
             "<ul><li>Sertifikat bo'lsa — aniq: <i>Ingliz tili — IELTS 6.5</i>, <i>Koreys tili — TOPIK 3</i>.</li>"
             "<li>Sertifikat bo'lmasa — xalqaro daraja: A1–A2 (boshlang'ich), B1–B2 (o'rta, gaplasha olaman), C1–C2 (erkin).</li>"
             "<li>Ona tilingizni ham yozing: <i>O'zbek — ona tili, Rus — B2</i>.</li></ul>"),
        ],
    },
    {
        "id": "yozish",
        "icon": "✍️",
        "title": "Rezyumega nima yoziladi",
        "items": [
            ("Rezyumeda qanday bo'limlar bo'lishi kerak?",
             "<ol><li><b>Ism, lavozim va aloqa</b> — telefon, email, shahar, Telegram.</li>"
             "<li><b>Qisqacha o'zingiz haqingizda</b> — 2–3 gap.</li>"
             "<li><b>Ish tajribasi</b> — oxirgi ishdan boshlab.</li>"
             "<li><b>Ta'lim</b>.</li>"
             "<li><b>Ko'nikmalar</b> va <b>tillar</b>.</li>"
             "<li>Bo'lsa: sertifikatlar, loyihalar, yutuqlar.</li></ol>"),
            ("Nimalarni yozish shart EMAS?",
             "<ul><li>Pasport ma'lumotlari, JShShIR, to'liq uy manzili (faqat shahar yetarli).</li>"
             "<li>Millat, din, oilaviy holat, bo'y-vazn — so'ralmasa, yozmang.</li>"
             "<li>Oldingi maoshingiz, ishdan ketish sabablari.</li>"
             "<li>«Kompyuterni bilaman» kabi umumiy gaplar — aniq dastur nomlarini yozing.</li></ul>"),
            ("Ish tajribasini qanday yozish to'g'ri?",
             "<p>Har bir ish joyi uchun: <b>lavozim, kompaniya, yillar</b> va 2–4 ta qisqa band — <b>nima qildingiz va qanday natija bo'ldi</b>.</p>"
             "<p>❌ <i>«Sotuv bilan shug'ullandim»</i><br>✅ <i>«Kuniga 40+ mijozga maslahat berdim, oylik sotuv rejasini 3 oy ketma-ket 110% bajardim»</i></p>"),
            ("Ko'nikmalar bo'limiga nima yozaman?",
             "<p>Vakansiyada so'ralgan narsalarni birinchi yozing. Ikki turga ajrating:</p>"
             "<ul><li><b>Kasbiy</b>: Excel, 1C, Canva, AutoCAD, Python, kassa apparati, B toifali haydovchilik guvohnomasi.</li>"
             "<li><b>Shaxsiy</b>: mijozlar bilan muloqot, jamoada ishlash, stressga chidamlilik — imkon bo'lsa misol bilan.</li></ul>"),
            ("Email manzil muhimmi?",
             "<p>Ha. <code>shirin_qiz_2001@mail.ru</code> o'rniga <code>dilnoza.karimova@gmail.com</code> kabi ism-familiyali email oching — 2 daqiqa ishi, lekin jiddiyroq ko'rinasiz.</p>"),
            ("ATS nima va rezyumem undan o'tadimi?",
             "<p>ATS — katta kompaniyalar arizalarni avtomatik saralaydigan dastur. U murakkab dizayn, jadval va rasmlar ichidagi matnni yaxshi o'qimaydi. "
             "Katta kompaniya yoki xalqaro vakansiyaga topshirsangiz, tezrezyume.uz'dagi <b>«ATS» belgili shablonlardan</b> foydalaning va vakansiyadagi kalit so'zlarni rezyumeda ishlating.</p>"),
            ("Har bir vakansiyaga alohida rezyume kerakmi?",
             "<p>Bir xil rezyumeni hammaga yuborish mumkin, lekin <b>moslashtirilgan</b> rezyume ancha ko'p javob oladi. "
             "tezrezyume.uz'da «Vakansiyaga moslashtirish» bo'limiga e'lon matnini qo'ysangiz, AI rezyumeni shu talablarga moslab qayta yozadi — asl nusxa o'zgarmaydi.</p>"),
        ],
    },
    {
        "id": "topshirish",
        "icon": "📨",
        "title": "Ishga qanday topshiraman",
        "items": [
            ("Vakansiyalarni qayerdan qidiraman?",
             "<ul><li><b>hh.uz</b> — eng katta ish saytlaridan biri, ko'p kompaniyalar shu yerda.</li>"
             "<li><b>Telegram kanallar</b> — shahar va soha bo'yicha ish kanallari (qidiruvda «vakansiya Toshkent», «ish bor» deb yozing).</li>"
             "<li><b>OLX.uz</b> — «Ish» bo'limi, ayniqsa xizmat va savdo sohasida.</li>"
             "<li><b>Kompaniyalarning saytlari va Instagram sahifalari</b> — «Karyera / Vakansiyalar» bo'limi.</li>"
             "<li><b>LinkedIn</b> — IT, xalqaro kompaniyalar va ingliz tilidagi ishlar uchun.</li>"
             "<li><b>Tanishlar</b> — do'st va qarindoshlarga ish qidirayotganingizni ayting, ko'p ishlar shunday topiladi.</li></ul>"),
            ("HR'ga Telegram'da nima deb yozaman?",
             "<p>Qisqa, salomlashib, aniq yozing va rezyumeni <b>PDF qilib biriktiring</b>. Namuna (nusxalab olishingiz mumkin):</p>"
             "<div class='tpl' data-copy>Assalomu alaykum! Men Dilnoza Karimova. «SMM menejer» vakansiyangizga topshirmoqchiman. "
             "3 yildan beri Instagram sahifalar yuritaman, Canva va Meta Ads bilan ishlayman. Rezyumemni ilova qildim. "
             "Suhbatga istalgan vaqtda kela olaman. Telefon: +998 90 123 45 67. Rahmat!</div>"
             "<p>Qilmang: faqat «Salom» yoki faqat faylni izohsiz tashlash, ovozli xabar yuborish, kechasi yozish.</p>"),
            ("Email orqali yuborsam, xatga nima yozaman?",
             "<p><b>Mavzu:</b> <i>SMM menejer vakansiyasiga — Dilnoza Karimova</i></p>"
             "<div class='tpl' data-copy>Assalomu alaykum!\n\nSizning kompaniyangizdagi «SMM menejer» vakansiyasiga topshirmoqchiman. "
             "3 yillik tajribam bor: brend sahifalarini yuritganman, reklama orqali obunachilarni 2 barobar oshirganman. "
             "Rezyumemni ilova qildim.\n\nSuhbat uchun qulay vaqtingizni yozsangiz, xursand bo'laman.\n\nHurmat bilan,\nDilnoza Karimova\n+998 90 123 45 67</div>"),
            ("Kuniga nechta ish joyiga topshirish kerak?",
             "<p>Sifat miqdordan muhimroq, lekin juda kam ham bo'lmasin. Faol qidiruvda <b>kuniga 3–10 ta</b> sizga mos vakansiyaga yuborish yaxshi natija beradi. "
             "Qayerga yuborganingizni oddiy ro'yxatda yozib boring: kompaniya, lavozim, sana, javob.</p>"),
            ("Javob kelmayapti. Qancha kutaman?",
             "<p>Odatda <b>3–7 ish kuni</b>. Javob bo'lmasa, bir marta xushmuomala eslatma yuborsa bo'ladi: "
             "<i>«Assalomu alaykum, o'tgan hafta SMM menejer vakansiyasiga rezyume yuborgan edim. Ko'rib chiqishga imkon bo'ldimi?»</i> "
             "Umuman javob bo'lmasa — xafa bo'lmang, bu ko'pincha siz bilan bog'liq emas, qidirishda davom eting.</p>"),
            ("Firibgar «ish beruvchi»larni qanday aniqlayman?",
             "<p>Ehtiyot bo'ling, agar:</p>"
             "<ul><li>Ishga olishdan oldin <b>pul so'rashsa</b> — «forma», «o'qish», «hujjat», «ro'yxatdan o'tish» uchun.</li>"
             "<li>Karta ma'lumotlari, SMS kod yoki pasport rasmini suhbatdan oldin so'rashsa.</li>"
             "<li>Ish haqi bozordagidan juda baland va talablar yo'q bo'lsa («uyda o'tirib kuniga 100$»).</li>"
             "<li>Chet elga ishga yuborishni rasmiy litsenziyasiz, naqd pul evaziga va'da qilishsa.</li></ul>"
             "<p>Haqiqiy ish beruvchi sizdan pul olmaydi — u sizga maosh to'laydi. Chet elda ishlash bo'yicha rasmiy ma'lumotni faqat davlat idoralarining rasmiy sayt va kanallaridan tekshiring.</p>"),
        ],
    },
    {
        "id": "suhbat",
        "icon": "🤝",
        "title": "Suhbat (intervyu)",
        "items": [
            ("Suhbatga qanday tayyorlanaman?",
             "<ul><li>Kompaniya haqida 10 daqiqa o'qing: nima qiladi, mahsulotlari, saytidagi «biz haqimizda».</li>"
             "<li>Vakansiya talablarini qayta o'qing va har biriga o'zingizdan bitta misol tayyorlang.</li>"
             "<li>Rezyumengizni yodda tuting — undagi har bir qatorni tushuntira olishingiz kerak.</li>"
             "<li>Manzil va vaqtni oldindan aniqlang, <b>10 daqiqa oldin</b> keling.</li>"
             "<li>O'zingiz ham 1–2 ta savol tayyorlang (pastda bor).</li></ul>"),
            ("«O'zingiz haqingizda gapirib bering» deyishsa nima deyman?",
             "<p>Hayot tarixi emas, <b>1 daqiqalik ish haqidagi hikoya</b>: hozir kimsiz → nimada tajribangiz yoki bilimingiz bor → nega aynan shu ishga kelgansiz.</p>"
             "<div class='tpl' data-copy>Men Dilnoza, iqtisodiyot yo'nalishini bitirganman. So'nggi 3 yil davomida kichik brendlarning Instagram sahifalarini yuritdim: kontent reja tuzdim, Canva'da dizayn qildim va reklama sozladim. Eng yaxshi natijam — bir do'kon sahifasini 6 oyda 2 ming obunachidan 15 mingga yetkazganim. Sizning kompaniyangizda kattaroq jamoada o'sishni xohlayman, shuning uchun topshirdim.</div>"),
            ("«Kamchiliklaringiz nima?» — qanday javob beraman?",
             "<p>«Kamchiligim yo'q» yoki «juda mehnatkashman» demang. Haqiqiy, lekin ishga xalal bermaydigan kamchilikni va uni qanday tuzatayotganingizni ayting: "
             "<i>«Oldin ommaviy chiqishlardan hayajonlanardim, shuning uchun jamoa yig'ilishlarida ko'proq gapirishga harakat qilyapman.»</i></p>"),
            ("Qancha maosh so'rash kerak?",
             "<ul><li>Oldindan hh.uz va Telegram kanallarda shu lavozim uchun maoshlarni ko'rib chiqing.</li>"
             "<li>Aniq bitta raqam emas, <b>oraliq</b> ayting: <i>«6–7 million so'm oralig'ida kutyapman»</i>.</li>"
             "<li>Tajribasiz bo'lsangiz: <i>«Birinchi o'rinda tajriba muhim, sizdagi shu lavozim uchun belgilangan maosh qancha?»</i> deb so'rasangiz ham bo'ladi.</li>"
             "<li>Maosh «qo'lga» (soliqdan keyin) yoki «soliqdan oldin» ekanini aniqlab oling.</li></ul>"),
            ("Suhbatga nima kiyib boraman?",
             "<p>Kompaniyaga qarab bir pog'ona rasmiyroq kiyining: bank va ofis uchun — klassik, IT va kreativ sohalar uchun — toza, tartibli kundalik kiyim. "
             "Asosiysi — toza, dazmollangan, qulay. Kuchli atir va ko'p aksessuarlardan saqlaning.</p>"),
            ("Onlayn (video) suhbat bo'lsa nimaga e'tibor beray?",
             "<ul><li>Internet, kamera va mikrofonni 15 daqiqa oldin tekshiring, telefon zaryadlangan bo'lsin.</li>"
             "<li>Tinch, yorug' joy tanlang, orqa fon oddiy bo'lsin.</li>"
             "<li>Kameraga qarab gapiring, bildirishnomalarni o'chiring.</li>"
             "<li>Havola ochilmasa, darhol HR'ga yozing — jim kutmang.</li></ul>"),
            ("Suhbat oxirida o'zim nima so'rashim mumkin?",
             "<ul><li>«Bu lavozimda birinchi oyda mendan qanday natija kutiladi?»</li>"
             "<li>«Ish kuni qanday o'tadi, jamoa necha kishi?»</li>"
             "<li>«Sinov muddati bormi va qancha?»</li>"
             "<li>«Keyingi bosqich qanday va javobni qachon kutsam bo'ladi?»</li></ul>"
             "<p>Birinchi suhbatning o'zida faqat maosh va ta'til haqida so'rashdan boshlamang.</p>"),
            ("Suhbatdan keyin nima qilaman?",
             "<p>Shu kuni qisqa rahmat xabari yuboring: <i>«Bugungi suhbat uchun rahmat! Lavozim menga yanada qiziq bo'ldi, javobingizni kutaman.»</i> "
             "Bu kichik narsa, lekin sizni boshqa nomzodlardan ajratib turadi.</p>"),
        ],
    },
    {
        "id": "rasmiy",
        "icon": "📑",
        "title": "Ishga qabul va hujjatlar",
        "items": [
            ("Ishga kirishda odatda qanday hujjatlar so'raladi?",
             "<ul><li>Pasport yoki ID-karta.</li>"
             "<li>Ta'lim hujjati (diplom, attestat) — lavozim talab qilsa.</li>"
             "<li>Harbiy hisob hujjati (yigitlar uchun, ko'p hollarda).</li>"
             "<li>Tibbiy ma'lumotnoma — oziq-ovqat, ta'lim, tibbiyot kabi sohalarda.</li>"
             "<li>Bank kartasi rekvizitlari — maosh uchun.</li></ul>"
             "<p>Aniq ro'yxatni kompaniyaning kadrlar bo'limidan so'rang.</p>"),
            ("Mehnat shartnomasi tuzilishi shartmi?",
             "<p>Ha, rasmiy ishga qabul yozma <b>mehnat shartnomasi</b> bilan bo'ladi. Unda lavozim, ish vaqti, maosh va sinov muddati yoziladi — imzolashdan oldin o'qing. "
             "Rasmiy ish staj, pensiya va ijtimoiy kafolatlar uchun muhim. Mehnat faoliyatingiz yozuvlarini «Yagona milliy mehnat tizimi» (my.mehnat.uz) orqali tekshirish mumkin.</p>"),
            ("Sinov muddati nima?",
             "<p>Ish beruvchi va siz bir-biringizni sinab ko'radigan davr. U shartnomada yoziladi va odatda <b>3 oydan oshmaydi</b>. "
             "Sinov muddatida ham siz rasmiy xodimsiz — maosh to'lanadi. Aniq qoidalar uchun amaldagi Mehnat kodeksiga yoki kadrlar bo'limiga murojaat qiling.</p>"),
            ("Bepul «stajirovka» yoki «sinov kuni» so'rashsa-chi?",
             "<p>1 kunlik tanishuv yoki kichik test topshiriq odatiy hol. Lekin bir necha hafta <b>bepul ishlatish</b>, ayniqsa haqiqiy ish (sotuv, yetkazib berish, smena) qildirish — "
             "shubhali. Qancha davom etishi va to'lanadimi — oldindan aniq so'rang va iloji bo'lsa yozma kelishing.</p>"),
        ],
    },
    {
        "id": "tezrezyume",
        "icon": "⚡",
        "title": "tezrezyume.uz haqida",
        "items": [
            ("Sayt qanday ishlaydi?",
             "<ol><li>Oddiy savollarga javob berasiz yoki o'zingiz haqingizda erkin yozasiz — bilmaganingizni o'tkazib yuborasiz.</li>"
             "<li>AI ~1 daqiqada tartibli, professional rezyume yozadi.</li>"
             "<li>tayyor namunadan boshlaysiz yoki shablonni tanlaysiz, kerak bo'lsa vakansiyaga moslashtirasiz.</li>"
             "<li>PDF yoki Word qilib yuklab olasiz.</li></ol>"),
            ("Bepulmi?",
             "<p>Rezyume yaratish, tayyor namunalar va <b>birinchi PDF — bepul</b> («Bepul» belgili shablonlarda). Word fayl, Pro shablonlar va ko'proq PDF uchun rezyumeni <b>kredit</b> bilan ochasiz yoki ko'p rezyume kerak bo'lsa <b>Pro</b> olasiz. "
             "Obuna yo'q, kredit muddati tugamaydi. Aniq narxlar <a href='/pricing/'>Narxlar</a> sahifasida.</p>"),
            ("AI rezyumemga yolg'on narsa qo'shib qo'yadimi?",
             "<p>Yo'q. AI faqat siz yozgan ma'lumotdan foydalanadi: jumlalarni chiroyli qiladi, tartiblaydi, imloni to'g'rilaydi. "
             "Siz aytmagan ish joyi, sana, diplom yoki sertifikatni o'ylab topmaydi. Vakansiyaga moslashtirishda sizda yo'q talablar alohida ko'rsatiladi, rezyumega qo'shilmaydi.</p>"),
            ("Ma'lumotlarim xavfsizmi?",
             "<p>Rezyumengizni faqat siz ko'rasiz. Ommaviy havolani o'zingiz yoqmaguningizcha uni hech kim ocha olmaydi, manzillar esa taxmin qilib bo'lmaydigan kod bilan yaratiladi. "
             "Parol yo'q — kirish Telegram orqali.</p>"),
            ("To'lov qanday qilinadi?",
             "<p>Hozircha Telegram bot orqali: botda paketni tanlaysiz → kartaga o'tkazasiz → chek rasmini yuborasiz → tekshirilgach kredit avtomatik qo'shiladi. "
             "Click va Payme ulanmoqda.</p>"),
            ("Telegram ichida PDF yuklanmayapti, nima qilay?",
             "<p>Rezyume sahifasidagi <b>«Telegram chatga yuborish»</b> tugmasini bosing — fayl bot xabarida keladi. Telegram ilovasini yangilash ham yordam beradi.</p>"),
            ("Savolim javobsiz qoldi. Kimga yozaman?",
             "<p><a href='/aloqa/'>Aloqa</a> sahifasi orqali yozing — odatda bir necha soat ichida javob beramiz.</p>"),
        ],
    },
]


def faq_schema(sections=SECTIONS):
    """Google uchun FAQPage strukturaviy ma'lumoti (HTML teglarsiz)."""
    import re
    from html import unescape

    def plain(html):
        return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()

    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": plain(a)}}
            for section in sections for q, a in section["items"]
        ],
    }


def plain_text(html):
    import re
    from html import unescape

    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def slugify_question(question):
    """«Diplomsiz ish topsa bo'ladimi?» → «diplomsiz-ish-topsa-boladimi» (o'zbek lotin harflari uchun)."""
    import re

    text = question.lower()
    for a, b in (("o‘", "o"), ("g‘", "g"), ("o'", "o"), ("g'", "g"), ("ʻ", ""), ("’", ""), ("'", ""), ("«", ""), ("»", "")):
        text = text.replace(a, b)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:80].rstrip("-")


def all_questions():
    """[(section, index, question, answer_html, slug)] — tartib bilan."""
    items = []
    for section in SECTIONS:
        for i, (q, a) in enumerate(section["items"], 1):
            items.append({"section": section, "n": f"{section['id']}-{i}", "q": q, "a": a, "slug": slugify_question(q)})
    return items


def find_question(slug):
    for item in all_questions():
        if item["slug"] == slug:
            return item
    return None
