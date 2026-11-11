"""سمارت ديلز (Smart Deals) — تطبيق أندرويد (Flet).
الرئيسية (عروض قوية + بحث) • العروض • الكوبونات • عن التطبيق.
المحتوى (عروض/كوبونات/مؤقت/معرّف التتبع) يُدار من لوحة التحكم عن بُعد."""
import threading
import time

import flet as ft

import amazon
import app_config
import remote

PRIMARY, VIOLET, ACCENT, MINT = "#5B5BD6", "#8B5CF6", "#FF5C7A", "#12B886"
BG, CARD, TEXT, MUTED, BORDER, GOLD, SOFT = "#F4F5FB", "#FFFFFF", "#14142B", "#6E6E8A", "#E6E8F2", "#F5A524", "#EEEDFF"
BTN_TEXT = "عرض السعر والتفاصيل على أمازون"
SUGGEST = ["سماعات", "هاتف", "ساعة ذكية", "عطر", "ألعاب", "أدوات مطبخ"]
_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")


def ic(name, fallback="CIRCLE"):
    return getattr(ft.Icons, name, None) or getattr(ft.Icons, fallback, None)


def fmt_remaining(sec):
    sec = max(0, int(sec))
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def fmt_left(sec):
    sec = max(0, int(sec))
    d, h, m = sec // 86400, sec % 86400 // 3600, sec % 3600 // 60
    if d:
        return f"{d} يوم" + (f" و{h} ساعة" if h else "")
    if h:
        return f"{h} ساعة" + (f" و{m} دقيقة" if m else "")
    return f"{max(m, 1)} دقيقة"


def to_num(s):
    try:
        return float(str(s or "").translate(_AR).replace(",", ".").strip())
    except ValueError:
        return None


def main(page: ft.Page):
    page.title = app_config.APP_NAME
    page.padding = 0
    page.spacing = 0
    page.bgcolor = BG
    try:
        page.theme_mode = ft.ThemeMode.LIGHT
        page.theme = ft.Theme(color_scheme_seed=PRIMARY)
    except Exception:
        pass

    st = {"query": "", "sort": "relevance", "min": None, "max": None, "page": 1, "has_more": False,
          "items": [], "busy": False, "gen": 0, "tab": 0}
    rem = {"data": remote.normalize({}), "status": "none"}
    local = remote.load_local()
    shown = {"coupons": None, "timer_key": None}

    # ================================================================ أدوات
    def cfg(key, default=""):
        return rem["data"]["config"].get(key, default)

    def tag():
        return str(cfg("affiliate_tag", "") or app_config.DEFAULT_AFFILIATE_TAG or "").strip()

    def show_prices():
        return cfg("show_prices", False) is True          # الافتراضي: الأسعار مخفية

    def toast(msg):
        try:
            page.open(ft.SnackBar(ft.Text(msg)))
        except Exception:
            pass

    def open_url(u):
        if u:
            page.launch_url(u)

    def shadow():
        try:
            return ft.BoxShadow(blur_radius=16, color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK), offset=ft.Offset(0, 4))
        except Exception:
            return None

    def btn(text, on_click, style="primary", icon=None, expand=False):
        fg = {"primary": "#FFFFFF", "soft": PRIMARY, "accent": "#FFFFFF"}[style]
        kw = {"gradient": ft.LinearGradient(colors=[PRIMARY, VIOLET])} if style == "primary" else \
             {"bgcolor": SOFT if style == "soft" else ACCENT}
        row = [ft.Text(text, size=14, weight=ft.FontWeight.W_600, color=fg, text_align=ft.TextAlign.CENTER)]
        if icon:
            row.append(ft.Icon(ic(icon), size=18, color=fg))
        return ft.Container(ft.Row(row, alignment=ft.MainAxisAlignment.CENTER, spacing=6), border_radius=14,
                            padding=ft.padding.symmetric(horizontal=16, vertical=12), ink=True, on_click=on_click,
                            expand=expand, alignment=ft.alignment.center, **kw)

    def pill(text, bg, fg="#FFFFFF"):
        return ft.Container(ft.Text(text, size=11, color=fg, weight=ft.FontWeight.BOLD), bgcolor=bg, border_radius=8,
                            padding=ft.padding.symmetric(horizontal=8, vertical=3))

    def chip(text, on, on_click):
        return ft.Container(ft.Text(text, size=12, color="#FFFFFF" if on else TEXT, weight=ft.FontWeight.W_600 if on else None),
                            bgcolor=PRIMARY if on else CARD, border=ft.border.all(1, PRIMARY if on else BORDER),
                            border_radius=18, padding=ft.padding.symmetric(horizontal=14, vertical=7), ink=True, on_click=on_click)

    def header(title, sub, extra=None, icon_name="LOCAL_OFFER"):
        badge = ft.Container(ft.Icon(ic(icon_name), color="#FFFFFF", size=22), width=42, height=42, border_radius=21,
                             bgcolor=ft.Colors.with_opacity(0.22, "#FFFFFF"), alignment=ft.alignment.center)
        col = [ft.Row([ft.Column([ft.Text(title, size=22, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                                  ft.Text(sub, size=12, color="#E0E7FF")], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),
                       badge], alignment=ft.MainAxisAlignment.END, spacing=10)]
        if extra is not None:
            col.append(extra)
        return ft.Container(ft.Column(col, spacing=12), padding=ft.padding.only(left=16, right=16, top=14, bottom=18),
                            gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right, colors=[PRIMARY, VIOLET]),
                            border_radius=ft.border_radius.only(bottom_left=28, bottom_right=28))

    def empty_box(icon_name, text, sub=""):
        return ft.Container(ft.Column([
            ft.Icon(ic(icon_name), size=56, color="#C4C7E0"),
            ft.Text(text, size=16, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER, color=TEXT),
            ft.Text(sub, size=12, color=MUTED, text_align=ft.TextAlign.CENTER) if sub else ft.Container()],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8), padding=28, alignment=ft.alignment.center)

    def section_title(text):
        return ft.Row([ft.Text(text, size=17, weight=ft.FontWeight.BOLD, color=TEXT)], alignment=ft.MainAxisAlignment.END)

    def thumb(url, size=92):
        fallback = ft.Icon(ic("IMAGE_NOT_SUPPORTED", "IMAGE"), color="#C4C7E0")
        inner = ft.Image(src=url, width=size, height=size, fit=ft.ImageFit.CONTAIN, error_content=fallback) if url else fallback
        return ft.Container(inner, width=size, height=size, border_radius=12, bgcolor="#F8F8FC", alignment=ft.alignment.center,
                            clip_behavior=ft.ClipBehavior.ANTI_ALIAS)

    def card_box(content):
        return ft.Container(content, bgcolor=CARD, border_radius=18, padding=14, border=ft.border.all(1, BORDER), shadow=shadow())

    # ================================================================ الرئيسية: بحث + عروض قوية
    query_f = ft.TextField(hint_text="ابحث عن أي منتج…", prefix_icon=ft.Icons.SEARCH, border_radius=28, filled=True,
                           bgcolor="#FFFFFF", color=TEXT, border_color="transparent", text_align=ft.TextAlign.RIGHT, expand=True,
                           content_padding=ft.padding.symmetric(horizontal=16, vertical=14), on_submit=lambda e: new_search())
    go_btn = ft.Container(ft.Icon(ic("ARROW_BACK"), color=PRIMARY), bgcolor="#FFFFFF", border_radius=24, width=48, height=48,
                          alignment=ft.alignment.center, ink=True, on_click=lambda e: new_search())
    announce = ft.Container(visible=False, bgcolor=SOFT, border_radius=14, padding=12)
    sort_row = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=6, alignment=ft.MainAxisAlignment.END, visible=False)
    min_f = ft.TextField(label="أقل سعر", width=110, text_size=13, on_change=lambda e: set_range())
    max_f = ft.TextField(label="أعلى سعر", width=110, text_size=13, on_change=lambda e: set_range())
    filter_tile = ft.ExpansionTile(title=ft.Text("تصفية السعر", size=13), visible=False, controls=[
        ft.Container(ft.Row([max_f, min_f], alignment=ft.MainAxisAlignment.END), padding=8)])
    progress = ft.ProgressBar(visible=False, color=PRIMARY)
    status = ft.Container(visible=False, border_radius=14, padding=12)
    results = ft.ListView(expand=True, spacing=12, padding=ft.padding.only(bottom=16))

    def paint_sort():
        row = [chip(t, st["sort"] == k, lambda e, k=k: set_sort(k)) for k, t, _ in amazon.SORTS]
        if show_prices():
            row.append(chip("أعلى خصم", st["sort"] == "discount", lambda e: set_sort("discount")))
        sort_row.controls = row
        filter_tile.visible = show_prices()

    def set_sort(k):
        st["sort"] = k
        paint_sort()
        if st["query"] and k != "discount":
            new_search(st["query"])                 # الترتيب يتم عند أمازون نفسها
        else:
            render()

    def set_range():
        st["min"], st["max"] = to_num(min_f.value), to_num(max_f.value)
        render()

    def visible_items():
        items = list(st["items"])
        if not show_prices():
            return items                            # ترتيب أمازون كما هو، دون استخدام أي أسعار
        lo, hi = st["min"], st["max"]
        if lo is not None or hi is not None:
            items = [i for i in items if i["price"] is None or ((lo is None or i["price"] >= lo) and (hi is None or i["price"] <= hi))]
        priced = [i for i in items if i["price"] is not None]
        unpriced = [i for i in items if i["price"] is None]
        k = st["sort"]
        if k == "price_desc":
            priced.sort(key=lambda i: -i["price"])
        elif k == "price_asc":
            priced.sort(key=lambda i: i["price"])
        elif k == "discount":
            priced.sort(key=lambda i: (-i["discount_pct"], i["price"]))
        return priced + unpriced

    def stars(it):
        if not it["rating"]:
            return ft.Container()
        n = f" ({it['reviews']:,})" if it.get("reviews") else ""
        return ft.Text(f"★ {it['rating']:.1f}{n}", size=12, color=GOLD, weight=ft.FontWeight.W_600)

    def product_card(it):
        info = [ft.Text(it["name"], size=14, color=TEXT, max_lines=3, overflow=ft.TextOverflow.ELLIPSIS, text_align=ft.TextAlign.RIGHT),
                stars(it)]
        if show_prices() and it["price"] is not None:
            info.append(ft.Row([ft.Text(f"{it['price']:,.2f}", size=21, weight=ft.FontWeight.BOLD, color=TEXT),
                                ft.Text("ر.س", size=12, color=MUTED)], spacing=4, alignment=ft.MainAxisAlignment.END))
            if it["old_price"]:
                info.append(ft.Row([pill(f"-{it['discount_pct']}%", ACCENT)], alignment=ft.MainAxisAlignment.END))
        if it["sponsored"]:
            info.append(ft.Text("ممول", size=10, color=MUTED))
        link = amazon.product_url(it["asin"], tag())
        return card_box(ft.Column([
            ft.Row([ft.Column(info, expand=True, spacing=4, horizontal_alignment=ft.CrossAxisAlignment.END), thumb(it["image"])],
                   vertical_alignment=ft.CrossAxisAlignment.START, spacing=12),
            ft.Row([btn(BTN_TEXT, lambda e, u=link: open_url(u), "primary", "OPEN_IN_NEW", expand=True)])], spacing=12))

    def hot_card(h):
        link = amazon.affiliate(h["url"], tag())
        info = [ft.Text(h["title"], size=15, weight=ft.FontWeight.W_600, color=TEXT, max_lines=3, overflow=ft.TextOverflow.ELLIPSIS,
                        text_align=ft.TextAlign.RIGHT)]
        if str(h.get("note", "")).strip():
            info.append(ft.Row([pill(str(h["note"]), ACCENT)], alignment=ft.MainAxisAlignment.END))
        return card_box(ft.Column([
            ft.Row([ft.Column(info, expand=True, spacing=6, horizontal_alignment=ft.CrossAxisAlignment.END), thumb(h.get("image", ""), 96)],
                   vertical_alignment=ft.CrossAxisAlignment.START, spacing=12),
            ft.Row([btn(BTN_TEXT, lambda e, u=link: open_url(u), "primary", "OPEN_IN_NEW", expand=True)])], spacing=12))

    def home_controls():
        out = []
        hot = rem["data"]["hot"]
        out.append(section_title("عروض قوية 🔥"))
        out += [hot_card(h) for h in hot] or [empty_box("LOCAL_FIRE_DEPARTMENT", "لا توجد عروض قوية الآن", "تابعنا، نضيف منتجات مميزة باستمرار.")]
        out.append(section_title("جرّب البحث عن"))
        out.append(ft.Row([chip(s, False, lambda e, s=s: run_query(s)) for s in SUGGEST], wrap=True, run_spacing=8, spacing=6,
                          alignment=ft.MainAxisAlignment.END))
        return out

    def show_status(msg, search_link=True):
        rows = [ft.Text(msg, size=13, color=TEXT, text_align=ft.TextAlign.RIGHT)]
        if search_link and st["query"]:
            rows.append(btn("افتح البحث في أمازون", lambda e: open_url(amazon.search_page_url(st["query"], tag())), "soft", "OPEN_IN_NEW"))
        status.content = ft.Column(rows, spacing=8, horizontal_alignment=ft.CrossAxisAlignment.END)
        status.bgcolor, status.visible = "#FFF1F3", True

    def render():
        if not st["query"]:
            sort_row.visible = False
            results.controls = home_controls()
        else:
            sort_row.visible = True
            items = visible_items()
            cards = [ft.Row([chip("مسح البحث ✕", False, lambda e: clear_search())], alignment=ft.MainAxisAlignment.END)]
            cards += [product_card(i) for i in items]
            if items and st["has_more"] and not st["busy"]:
                cards.append(btn("عرض المزيد من النتائج", lambda e: more(), "soft", "ADD"))
            if not items and not st["busy"] and not status.visible:
                cards.append(empty_box("SEARCH_OFF", "لا توجد نتائج", "جرّب كلمة أخرى."))
            results.controls = cards
        page.update()

    def clear_search():
        st.update(query="", items=[], busy=False, gen=st["gen"] + 1)
        status.visible = False
        progress.visible = False
        query_f.value = ""
        render()

    def fetch_page(gen, pg):
        try:
            res = amazon.search(st["query"], pg, next((s for k, _, s in amazon.SORTS if k == st["sort"]), ""))
            if gen != st["gen"]:
                return
            known = {i["asin"] for i in st["items"]}
            st["items"] += [i for i in res["items"] if i["asin"] not in known]
            st["has_more"], st["page"] = res["has_more"], pg
        except amazon.AmazonError as e:
            if gen == st["gen"]:
                show_status(str(e) + (" يمكنك متابعة التسوق مباشرة عبر أمازون." if e.code != "network" else ""), e.code != "network")
        except Exception as e:
            if gen == st["gen"]:
                show_status(f"حدث خطأ غير متوقع: {e}")
        finally:
            if gen == st["gen"]:
                st["busy"] = False
                progress.visible = False
                render()

    def new_search(q=None):
        q = (q if isinstance(q, str) else query_f.value or "").strip()
        if not q:
            return toast("اكتب اسم المنتج أولاً")
        go(0)
        if cfg("search_mode", "app") == "link":      # وضع بلا جلب: يفتح أمازون مباشرة برابط عمولتك
            sort_param = next((s for k, _, s in amazon.SORTS if k == st["sort"]), "")
            open_url(amazon.search_page_url(q, tag(), sort_param))
            return toast("تم فتح نتائج البحث في أمازون")
        st.update(query=q, items=[], page=1, has_more=False, busy=True, gen=st["gen"] + 1)
        status.visible = False
        progress.visible = True
        paint_sort()
        page.update()
        threading.Thread(target=fetch_page, args=(st["gen"], 1), daemon=True).start()
        render()

    def run_query(q):
        query_f.value = q
        new_search(q)

    def more():
        if st["busy"]:
            return
        st["busy"] = True
        progress.visible = True
        page.update()
        threading.Thread(target=fetch_page, args=(st["gen"], st["page"] + 1), daemon=True).start()

    home_view = ft.Column(expand=True, spacing=0, controls=[
        header(app_config.APP_NAME, "كل العروض في مكان واحد", ft.Row([go_btn, query_f], spacing=8)),
        ft.Container(expand=True, padding=ft.padding.only(left=14, right=14, top=12), content=ft.Column(
            expand=True, spacing=10, controls=[announce, sort_row, filter_tile, progress, status, results]))])

    # ================================================================ العروض
    offers_list = ft.Column(spacing=12)

    def build_offers():
        rows = []
        for o in rem["data"]["offers"]:
            link = amazon.affiliate(o["url"], tag())
            rows.append(card_box(ft.Column([
                ft.Row([ft.Text(o["title"], size=16, weight=ft.FontWeight.BOLD, color=TEXT, expand=True, text_align=ft.TextAlign.RIGHT),
                        ft.Icon(ic("LOCAL_OFFER", "STAR"), color=ACCENT)], vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Row([btn("اذهب للعرض على أمازون", lambda e, u=link: open_url(u), "primary", "OPEN_IN_NEW", expand=True)])], spacing=12)))
        offers_list.controls = rows or [empty_box("LOCAL_OFFER", "لا توجد عروض الآن", "تابعنا، نضيف عروضاً جديدة باستمرار.")]

    offers_view = ft.Column(expand=True, spacing=0, visible=False, controls=[
        header("العروض والخصومات", "عروض متجددة", icon_name="LOCAL_OFFER"),
        ft.Container(expand=True, padding=ft.padding.only(left=14, right=14, top=12), content=ft.Column(
            expand=True, scroll=ft.ScrollMode.AUTO, spacing=12, controls=[offers_list]))])

    # ================================================================ الكوبونات
    coupons_list = ft.Column(spacing=12)
    timer_slot = ft.Column()
    channel_slot = ft.Column()
    timer_digits = ft.Text("", size=34, weight=ft.FontWeight.BOLD, color="#FFFFFF")

    def active_coupons():
        now = remote.server_now()
        return [c for c in rem["data"]["coupons"] if not (c.get("expires_ts") and c["expires_ts"] <= now)]   # الحذف التلقائي عند الانتهاء

    def timer_left():
        t = rem["data"]["timer"]
        return (t["end_ts"] - remote.server_now()) if t else 0

    def copy_code(c):
        try:
            page.set_clipboard(c["code"])
            toast(f"تم نسخ الكود: {c['code']}")
        except Exception:
            toast("تعذّر النسخ")

    def alert(title, body):
        dlg = ft.AlertDialog(title=ft.Text(title), content=ft.Text(body, text_align=ft.TextAlign.RIGHT),
                             actions=[ft.TextButton("عرض الكوبونات", on_click=lambda e: (page.close(dlg), go(2))),
                                      ft.TextButton("إغلاق", on_click=lambda e: page.close(dlg))])
        page.open(dlg)

    def set_notify(on):
        local["notify"] = bool(on)
        if on:
            local["seen"] = sorted(set(local["seen"]) | {c["id"] for c in active_coupons()})
        remote.save_local(local)
        toast("تم تفعيل التنبيهات — ستصلك أثناء فتح التطبيق" if on else "تم إيقاف التنبيهات")

    def check_new_coupons():
        cur = active_coupons()
        new = [c for c in cur if c["id"] not in local["seen"]]
        if new and local["notify"]:
            alert("كود خصم جديد 🎉", "، ".join((c.get("name") or "كود جديد") for c in new[:3]))
        local["seen"] = sorted(set(local["seen"]) | {c["id"] for c in cur})[-300:]
        remote.save_local(local)

    notify_sw = ft.Switch(value=local["notify"], on_change=lambda e: set_notify(e.control.value))
    notify_card = card_box(ft.Row([notify_sw, ft.Column([
        ft.Text("فعّل التنبيهات حتى لا يفوتك شيء", size=14, weight=ft.FontWeight.W_600, color=TEXT),
        ft.Text("تنبيه فوري بالكود الجديد وانتهاء المؤقت أثناء فتح التطبيق", size=11, color=MUTED)],
        expand=True, spacing=2, horizontal_alignment=ft.CrossAxisAlignment.END)], vertical_alignment=ft.CrossAxisAlignment.CENTER))

    def build_coupons():
        t = rem["data"]["timer"]
        timer_slot.controls = []
        if t and timer_left() > 0:
            timer_digits.value = fmt_remaining(timer_left())
            timer_slot.controls = [ft.Container(ft.Column([
                ft.Text(t["text"], size=15, color="#E0E7FF", weight=ft.FontWeight.W_600), timer_digits],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2), border_radius=18, padding=16,
                alignment=ft.alignment.center, gradient=ft.LinearGradient(colors=[PRIMARY, VIOLET]))]
        channel_slot.controls = [btn("تابع قناتنا ليصلك كل جديد", lambda e: open_url(cfg("channel_url")), "soft", "CAMPAIGN")] \
            if str(cfg("channel_url", "")).strip() else []
        rows, now = [], remote.server_now()
        cur = active_coupons()
        shown["coupons"] = tuple(c["id"] for c in cur)
        for c in cur:
            exp = c.get("expires_ts")
            badge_ = pill(f"ينتهي بعد {fmt_left(exp - now)}", MINT) if exp else pill("سينتهي قريباً", ACCENT)
            rows.append(card_box(ft.Column([
                ft.Row([badge_, ft.Text(c.get("name") or "كود خصم", size=15, weight=ft.FontWeight.BOLD, color=TEXT,
                                         expand=True, text_align=ft.TextAlign.RIGHT)], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(ft.Text(c["code"], size=21, weight=ft.FontWeight.BOLD, color=PRIMARY, selectable=True,
                                     text_align=ft.TextAlign.CENTER), bgcolor=SOFT, border=ft.border.all(1.5, VIOLET),
                             border_radius=12, padding=ft.padding.symmetric(vertical=12), alignment=ft.alignment.center),
                ft.Row([btn("نسخ الكود", lambda e, c=c: copy_code(c), "primary", "CONTENT_COPY", expand=True)]),
                ft.Text("الصق الكود عند الدفع على أمازون.", size=11, color=MUTED, text_align=ft.TextAlign.CENTER)],
                spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)))
        coupons_list.controls = rows or [empty_box("CONFIRMATION_NUMBER", "لا يوجد كود خصم الآن", "سنعرض الأكواد هنا فور توفرها.")]

    coupons_view = ft.Column(expand=True, spacing=0, visible=False, controls=[
        header("كوبونات الخصم", "انسخ الكود بضغطة واحدة", icon_name="CONFIRMATION_NUMBER"),
        ft.Container(expand=True, padding=ft.padding.only(left=14, right=14, top=12), content=ft.Column(
            expand=True, scroll=ft.ScrollMode.AUTO, spacing=12, controls=[notify_card, timer_slot, channel_slot, coupons_list]))])

    # ================================================================ عن التطبيق
    about_col = ft.Column(spacing=12)

    def build_about():
        rows = [card_box(ft.Column([
            ft.Text(f"{app_config.APP_NAME} ({app_config.APP_NAME_EN})", size=17, weight=ft.FontWeight.BOLD, color=TEXT),
            ft.Text("تطبيق يجمع لك أفضل العروض وكوبونات الخصم، ويساعدك على الوصول إلى المنتجات على أمازون بسهولة. "
                    "الأسعار والتفاصيل النهائية تظهر دائماً في صفحة المنتج على أمازون.",
                    size=12, color=MUTED, text_align=ft.TextAlign.RIGHT)], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.END)),
            ft.Container(ft.Column([ft.Text("إفصاح التسويق بالعمولة", size=13, weight=ft.FontWeight.BOLD, color=PRIMARY),
                                    ft.Text(app_config.DISCLOSURE, size=13, color=TEXT, text_align=ft.TextAlign.RIGHT)],
                                   spacing=4, horizontal_alignment=ft.CrossAxisAlignment.END),
                         bgcolor=SOFT, border_radius=14, padding=14),
            ft.Text(app_config.TRADEMARK, size=11, color=MUTED, text_align=ft.TextAlign.CENTER)]
        if cfg("privacy_url"):
            rows.append(btn("سياسة الخصوصية", lambda e: open_url(cfg("privacy_url")), "soft", "PRIVACY_TIP"))
        if cfg("contact"):
            rows.append(ft.Text(f"للتواصل: {cfg('contact')}", size=13, color=TEXT, selectable=True, text_align=ft.TextAlign.CENTER))
        rows.append(btn("تحديث المحتوى", lambda e: refresh_remote(True), "soft", "REFRESH"))
        if rem["status"] == "not_configured":
            rows.append(ft.Text("تنبيه للمشرف: لم يُضبط رابط قاعدة البيانات في app_config.py", size=11, color=ACCENT, text_align=ft.TextAlign.CENTER))
        elif rem["status"] in ("cache", "none"):
            rows.append(ft.Text("تعذّر تحديث المحتوى من الإنترنت" + (" — يُعرض آخر محتوى محفوظ." if rem["status"] == "cache" else "."),
                                size=11, color=MUTED, text_align=ft.TextAlign.CENTER))
        rows.append(ft.Text(f"الإصدار {app_config.VERSION}", size=11, color=MUTED, text_align=ft.TextAlign.CENTER))
        about_col.controls = rows

    about_view = ft.Column(expand=True, spacing=0, visible=False, controls=[
        header("عن التطبيق", "معلومات وإفصاح", icon_name="INFO_OUTLINE"),
        ft.Container(expand=True, padding=ft.padding.only(left=14, right=14, top=12), content=ft.Column(
            expand=True, scroll=ft.ScrollMode.AUTO, spacing=12, controls=[about_col]))])

    # ================================================================ المحتوى البعيد والمؤقت
    def apply_remote():
        a = cfg("announcement", "")
        announce.visible = bool(str(a).strip())
        announce.content = ft.Text(str(a), size=13, color=TEXT, text_align=ft.TextAlign.RIGHT)
        paint_sort()
        build_offers()
        build_coupons()
        build_about()
        check_new_coupons()
        render()

    def refresh_remote(manual=False):
        def work():
            data, status_ = remote.fetch()
            for x in data["offers"] + data["hot"]:           # أي رابط مختصر يُحوَّل لرابط كامل قبل إضافة معرّفك
                if "amazon." not in x["url"].lower():
                    amazon.expand_short(x["url"])
            rem["data"], rem["status"] = data, status_
            apply_remote()
            if manual:
                toast("تم التحديث" if status_ == "ok" else "تعذّر التحديث من الإنترنت")
        threading.Thread(target=work, daemon=True).start()

    def ticker():
        n = 0
        while True:
            time.sleep(1)
            n += 1
            try:
                t = rem["data"]["timer"]
                if t:
                    left = timer_left()
                    if left > 0 and st["tab"] == 2:
                        timer_digits.value = fmt_remaining(left)
                        page.update()
                    elif left <= 0 and shown["timer_key"] != t["end_ts"]:
                        shown["timer_key"] = t["end_ts"]
                        if local["notify"] and left > -120:
                            alert("انتهى المؤقت ⏰", f"{t['text']}: الكوبون متاح الآن، تحقق من القائمة.")
                        refresh_remote()
                        n = 0
                if tuple(c["id"] for c in active_coupons()) != shown["coupons"]:    # انتهت صلاحية كوبون: يختفي تلقائياً
                    build_coupons()
                    page.update()
                if n >= 60:
                    n = 0
                    refresh_remote()
            except Exception:
                pass

    # ================================================================ التنقل
    views = [home_view, offers_view, coupons_view, about_view]
    nav_row = ft.Row(alignment=ft.MainAxisAlignment.SPACE_AROUND)
    disc_strip = ft.Container(ft.Text(app_config.DISCLOSURE, size=10, color=MUTED, text_align=ft.TextAlign.CENTER),
                              bgcolor=CARD, padding=ft.padding.symmetric(horizontal=12, vertical=6),
                              border=ft.border.only(top=ft.BorderSide(1, BORDER)))

    def paint_nav():
        items = [("HOME", "الرئيسية"), ("LOCAL_OFFER", "العروض"), ("CONFIRMATION_NUMBER", "الكوبونات"), ("INFO_OUTLINE", "عن التطبيق")]
        nav_row.controls = [ft.Container(ft.Column([
            ft.Icon(ic(n, "CIRCLE"), size=24, color=PRIMARY if st["tab"] == i else "#9A9CB8"),
            ft.Text(lbl, size=11, color=PRIMARY if st["tab"] == i else "#9A9CB8", weight=ft.FontWeight.BOLD if st["tab"] == i else None)],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2), padding=ft.padding.symmetric(horizontal=14, vertical=6),
            border_radius=14, ink=True, bgcolor=SOFT if st["tab"] == i else None, on_click=lambda e, i=i: go(i))
            for i, (n, lbl) in enumerate(items)]

    def go(i):
        st["tab"] = i
        for j, v in enumerate(views):
            v.visible = (j == i)
        paint_nav()
        if i == 2:
            build_coupons()
        page.update()

    # ================================================================ التركيب
    paint_sort()
    build_offers()
    build_coupons()
    build_about()
    render()
    paint_nav()
    page.add(ft.SafeArea(expand=True, content=ft.Column(expand=True, spacing=0, controls=[
        ft.Column(views, expand=True, spacing=0), disc_strip,
        ft.Container(nav_row, bgcolor=CARD, padding=ft.padding.only(top=6, bottom=6), shadow=shadow())])))
    refresh_remote()
    threading.Thread(target=ticker, daemon=True).start()


ft.app(target=main)
