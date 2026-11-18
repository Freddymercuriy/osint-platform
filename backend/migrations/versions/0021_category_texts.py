"""Kategoriyalar: atama izohi (`explain_*`) va tavsiya etilgan harakat (`action_*`) — uz / ru / en

Rahbariyat kanali postlarida: "ransomware", "fishing" kabi atama birinchi uchraganda qisqa izoh (yig'iladigan
iqtibosda) va "Tavsiya:" satri. O'zbek kirill boshqa joylardagidek o'zbek lotinidan hosil qilinadi. Admin kategoriya
formasida tahrirlaydi; seed faqat bo'sh maydonlarni to'ldiradi.

Revision ID: 0021_category_texts
Revises: 0020_publishing
Create Date: 2026-11-17
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_category_texts"
down_revision: str | None = "0020_publishing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LANGS = ("uz", "ru", "en")

# slug: ((explain uz, ru, en), (action uz, ru, en))
TEXTS: dict[str, tuple[tuple[str, str, str], tuple[str, str, str]]] = {
    "ransomware": (
        ("Ransomware — tashkilot ma'lumotlarini shifrlab yoki o'g'irlab, qaytarish yoki oshkor qilmaslik uchun pul "
         "talab qiladigan hujum.",
         "Программа-вымогатель (ransomware) — атака, при которой злоумышленники шифруют или похищают данные "
         "организации и требуют выкуп.",
         "Ransomware — an attack in which criminals encrypt or steal an organisation's data and demand payment."),
        ("Tashkilot bilan bog'lanib holatni aniqlash; to'lov qilmaslik; zaxira nusxalar va kirish huquqlarini "
         "tekshirish; mijozlarni soxta xabar va qo'ng'iroqlardan ogohlantirish.",
         "Связаться с организацией и уточнить ситуацию; не платить выкуп; проверить резервные копии и доступы; "
         "предупредить клиентов о поддельных сообщениях и звонках.",
         "Contact the organisation to confirm the situation; do not pay; check backups and access rights; warn "
         "customers about fake messages and calls."),
    ),
    "darkweb-sale": (
        ("Dark web savdosi — o'g'irlangan ma'lumot yoki tizimga kirish huquqi yashirin forumlarda sotuvga qo'yilgani "
         "haqidagi e'lon.",
         "Продажа в даркнете — объявление о продаже украденных данных или доступа к системам на закрытых форумах.",
         "Dark-web sale — an offer of stolen data or access to systems on underground forums."),
        ("Tashkilotni ogohlantirish; parollar va masofaviy kirishni (VPN, RDP) tekshirib almashtirish; e'lonni "
         "kiberxavfsizlik xizmati orqali tasdiqlash.",
         "Предупредить организацию; проверить и сменить пароли и удалённый доступ (VPN, RDP); подтвердить "
         "объявление через службу кибербезопасности.",
         "Warn the organisation; check and rotate passwords and remote access (VPN, RDP); have the security team "
         "verify the offer."),
    ),
    "leak": (
        ("Ma'lumotlar sizib chiqishi — shaxsiy yoki tijorat ma'lumotlari ruxsatsiz oshkor bo'lishi yoki tarqatilishi.",
         "Утечка данных — несанкционированное раскрытие или распространение персональных или коммерческих данных.",
         "Data leak — personal or business data exposed or shared without authorisation."),
        ("Sizib chiqqan ma'lumot haqiqiyligi va hajmini aniqlash; zarar ko'rgan foydalanuvchilar parollarini "
         "almashtirish; zarur bo'lsa vakolatli organlarga xabar berish.",
         "Установить подлинность и объём утечки; сменить пароли затронутых пользователей; при необходимости "
         "уведомить уполномоченные органы.",
         "Verify whether the data is genuine and how much leaked; reset affected users' passwords; notify the "
         "authorities if required."),
    ),
    "credentials": (
        ("O'g'irlangan login va parollar — hisoblarga kirish uchun ishlatilishi mumkin bo'lgan ma'lumotlar (ko'pincha "
         "stiler dasturlar yig'adi).",
         "Украденные учётные данные — логины и пароли, которыми можно войти в аккаунты (часто их собирают "
         "программы-стилеры).",
         "Stolen credentials — logins and passwords that can be used to break into accounts (often harvested by "
         "info-stealer malware)."),
        ("Tegishli hisoblar parollarini almashtirish va ikki bosqichli autentifikatsiyani yoqish; shubhali kirishlarni "
         "tekshirish.",
         "Сменить пароли затронутых учётных записей и включить двухфакторную аутентификацию; проверить "
         "подозрительные входы.",
         "Reset the affected accounts' passwords and turn on two-factor authentication; review suspicious logins."),
    ),
    "phishing": (
        ("Fishing — bank, davlat xizmati yoki kompaniya nomidan soxta sayt yoki xabar orqali login, parol yoki karta "
         "ma'lumotlarini aldab olish.",
         "Фишинг — выманивание логинов, паролей или данных карт через поддельные сайты и сообщения от имени банка, "
         "госслужбы или компании.",
         "Phishing — tricking people into giving away logins, passwords or card details through fake sites or "
         "messages that pose as a bank, government service or company."),
        ("Soxta saytni yopish uchun xosting provayderi va UZCERT ga murojaat qilish; xodimlar va mijozlarni "
         "ogohlantirish.",
         "Обратиться к хостинг-провайдеру и в UZCERT, чтобы закрыть поддельный сайт; предупредить сотрудников и "
         "клиентов.",
         "Ask the hosting provider and UZCERT to take the fake site down; warn staff and customers."),
    ),
    "fraud": (
        ("Kiberfiribgarlik — internet yoki telefon orqali aldab pul yoki ma'lumot olish.",
         "Кибермошенничество — обман с целью получить деньги или данные через интернет или телефон.",
         "Cyber fraud — deceiving people online or by phone to get money or data."),
        ("Mijozlar va xodimlarni firibgarlik usuli haqida ogohlantirish; shubhali to'lovlarni bank bilan tekshirish.",
         "Предупредить клиентов и сотрудников о схеме мошенничества; проверить подозрительные платежи с банком.",
         "Warn customers and staff about the scheme; check suspicious payments with the bank."),
    ),
    "malware": (
        ("Zararli dastur — kompyuter yoki telefonga o'rnatilib, ma'lumot o'g'irlaydigan, josuslik qiladigan yoki "
         "tizimni buzadigan dastur.",
         "Вредоносная программа — программа, которая крадёт данные, шпионит или выводит систему из строя.",
         "Malware — software that steals data, spies on users or damages systems once installed."),
        ("Antivirus va EDR yangilanganini tekshirish; noma'lum fayl va havolalarni ochmaslik haqida xodimlarni "
         "ogohlantirish.",
         "Проверить, что антивирус и EDR обновлены; напомнить сотрудникам не открывать неизвестные файлы и ссылки.",
         "Make sure antivirus and EDR are up to date; remind staff not to open unknown files or links."),
    ),
    "vulnerability": (
        ("Zaiflik — dasturdagi xato bo'lib, hujumchiga tizimni egallash yoki ma'lumot olish imkonini beradi; hujumlarda "
         "faol ishlatilayotgan bo'lsa xavf yuqori.",
         "Уязвимость — ошибка в программе, позволяющая злоумышленнику захватить систему или получить данные; если её "
         "уже используют в атаках, риск высокий.",
         "Vulnerability — a software flaw that lets an attacker take over a system or reach data; the risk is high "
         "when it is already being exploited."),
        ("Shu dastur ishlatilayotgan tizimlarni aniqlash va yangilanishni zudlik bilan o'rnatish; o'rnatib bo'lmasa — "
         "ishlab chiqaruvchi tavsiya etgan himoya choralarini qo'llash.",
         "Найти системы, где используется этот продукт, и срочно установить обновление; если нельзя — применить меры "
         "защиты, рекомендованные производителем.",
         "Find the systems that run this product and install the update urgently; if that is not possible, apply the "
         "vendor's recommended mitigations."),
    ),
    "ddos-outage": (
        ("DDoS / uzilish — saytlar yoki internet xizmatlari hujum yoki nosozlik tufayli ishlamay qolishi.",
         "DDoS / сбой — недоступность сайтов или интернет-сервисов из-за атаки или неисправности.",
         "DDoS / outage — websites or internet services going down because of an attack or a failure."),
        ("Muhim xizmatlar ishlashini tekshirish; provayder bilan DDoS himoyasini kuchaytirish; mijozlarga xizmat holati "
         "haqida xabar berish.",
         "Проверить работу ключевых сервисов; усилить защиту от DDoS у провайдера; сообщить клиентам о статусе "
         "сервисов.",
         "Check that key services are up; strengthen DDoS protection with the provider; tell customers about service "
         "status."),
    ),
    "defacement": (
        ("Defeys — hujumchilar saytning sahifasini o'z xabari bilan almashtirishi.",
         "Дефейс — подмена страницы сайта сообщением злоумышленников.",
         "Defacement — attackers replacing a website's page with their own message."),
        ("Saytni tiklash va kirish yo'lini (parol, zaif plagin) aniqlab yopish; boshqa saytlarni ham tekshirish.",
         "Восстановить сайт, найти и закрыть путь проникновения (пароль, уязвимый плагин); проверить другие сайты.",
         "Restore the site and find and close the way in (password, vulnerable plug-in); check other sites too."),
    ),
    "espionage": (
        ("Kiberjosuslik — davlat bilan bog'liq guruhlarning maxfiy ma'lumot olish uchun uzoq muddatli yashirin "
         "hujumlari.",
         "Кибершпионаж — длительные скрытые атаки групп, связанных с государствами, ради секретных данных.",
         "Cyber-espionage — long, stealthy attacks by state-linked groups to obtain confidential information."),
        ("Hisobotdagi belgilar (IOC) bo'yicha tarmoqni tekshirishni kiberxavfsizlik xizmatiga topshirish; muhim "
         "xodimlar pochtasini kuzatuvga olish.",
         "Поручить службе кибербезопасности проверить сеть по индикаторам (IOC) из отчёта; усилить контроль почты "
         "ключевых сотрудников.",
         "Ask the security team to check the network for the report's indicators (IOCs); watch key staff mailboxes "
         "closely."),
    ),
    "law-enforcement": (
        ("Huquqni muhofaza qilish — kiberjinoyatchilarni ushlash, sud yoki rasmiy tergov haqidagi xabar.",
         "Правоохранительные действия — задержания, суды или официальные расследования киберпреступлений.",
         "Law enforcement — arrests, court cases or official investigations of cybercrime."),
        ("Ma'lumot uchun; o'z tashkilotimizga aloqasi bor-yo'qligini aniqlash.",
         "Для сведения; выяснить, касается ли это нашей организации.",
         "For information; check whether it concerns our organisation."),
    ),
    "advisory": (
        ("Ogohlantirish — CERT yoki davlat organining rasmiy tavsiyasi.",
         "Предупреждение — официальная рекомендация CERT или госоргана.",
         "Advisory — official guidance from a CERT or a government body."),
        ("Tavsiyani mas'ul xodimlarga yetkazish va bajarilishini nazorat qilish.",
         "Передать рекомендацию ответственным сотрудникам и проконтролировать выполнение.",
         "Pass the guidance to the responsible staff and follow up."),
    ),
    "research": (
        ("Tadqiqot — kiberxavfsizlik kompaniyalarining tahlil va hisobotlari.",
         "Исследование — аналитика и отчёты компаний по кибербезопасности.",
         "Research — analysis and reports from cyber-security companies."),
        ("Ma'lumot uchun; kiberxavfsizlik xizmati xulosasini so'rash.",
         "Для сведения; запросить вывод у службы кибербезопасности.",
         "For information; ask the security team for its assessment."),
    ),
    "other": (
        ("", "", ""),
        ("Ma'lumot uchun.", "Для сведения.", "For information."),
    ),
}


def upgrade() -> None:
    for kind in ("explain", "action"):
        for lang in LANGS:
            op.add_column("categories", sa.Column(f"{kind}_{lang}", sa.Text(), server_default="", nullable=False))
    conn = op.get_bind()
    for slug, (explain, action) in TEXTS.items():
        for i, lang in enumerate(LANGS):
            conn.execute(sa.text(
                f"update categories set explain_{lang} = case when explain_{lang} = '' then :e else explain_{lang} end, "
                f"action_{lang} = case when action_{lang} = '' then :a else action_{lang} end where slug = :s"
            ), {"e": explain[i], "a": action[i], "s": slug})


def downgrade() -> None:
    for kind in ("explain", "action"):
        for lang in LANGS:
            op.drop_column("categories", f"{kind}_{lang}")
