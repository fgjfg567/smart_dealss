# سمارت ديلز (Smart Deals) — دليل التشغيل الكامل

## ما هذا المشروع؟
- **التطبيق** (Flet / أندرويد): الرئيسية (عروض قوية + بحث) • العروض • الكوبونات • عن التطبيق.
- **لوحة التحكم** (`admin/index.html`): تتحكم بالمحتوى من أي متصفح، وتظهر التغييرات في التطبيق خلال دقيقة تقريباً بدون تحديث من المتجر.
- **الخادم**: قاعدة Firebase Realtime Database (مجانية). التطبيق يقرأ منها، واللوحة تكتب فيها.

## 1) إعداد Firebase (مرة واحدة)
1. console.firebase.google.com ← **Add project** (عطّل Analytics).
2. **Build ← Realtime Database ← Create database** ← **Locked mode**. انسخ رابط القاعدة (يشبه `https://xxxx-default-rtdb.firebaseio.com`).
3. **Build ← Authentication ← Get started ← Email/Password ← Enable**.
4. تبويب **Users ← Add user**: أنشئ حساب المشرف (بريدك + كلمة مرور قوية). انسخ **User UID** بجانبه.
5. **Project settings ⚙️ ← General ← Your apps ← </> (Web)**: سجّل تطبيق ويب وانسخ **apiKey**.
6. **Realtime Database ← Rules**: الصق محتوى `firebase_rules.json` بعد استبدال `ضع_هنا_UID_حساب_المشرف` بالـ UID ← **Publish**.

## 2) ضبط التطبيق
في `app_config.py` ضع `FIREBASE_DB_URL` (رابط الخطوة 2). معرّف التتبع تضبطه من لوحة التحكم.

## 3) الدخول إلى لوحة التحكم
- افتح `admin/index.html` (من المتصفح مباشرة، أو ارفعه على GitHub Pages لتدخل من أي مكان).
- أول مرة: الصق **apiKey** ورابط القاعدة (يُحفظان في متصفحك)، ثم بريد وكلمة مرور المشرف.
- **لا يوجد إنشاء حساب من اللوحة**: حساب المشرف يُنشأ يدوياً من Firebase (الخطوة 4)، وقواعد القاعدة تسمح بالكتابة لهذا الحساب وحده.
- نسيت كلمة المرور: Firebase ← Authentication ← Users ← ⋮ ← Reset password.

## 4) المستخدمون
لا يوجد تسجيل ولا حسابات للمستخدمين: يفتح التطبيق ويستخدمه مباشرة، ولا نجمع أي بيانات شخصية (يسهّل نموذج Data safety في Google Play).

## 5) بناء APK على GitHub (مشروع جديد)
1. github.com ← **+ ← New repository** ← الاسم `smart-deals` ← **Public** ← **Create repository**.
2. **uploading an existing file**: افتح المجلد بعد فك الضغط واسحب **محتوياته** (`src` و`admin` و`pyproject.toml` و`firebase_rules.json` ...) — وليس المجلد الخارجي نفسه ← **Commit changes**.
3. مجلد `.github` المخفي غالباً لا يُرفع. أنشئه: **Add file ← Create new file**، واكتب في خانة الاسم بالضبط `.github/workflows/build.yml` (النقطة قبل github)، والصق محتوى `github_workflow_build.yml` ← **Commit changes**.
4. تبويب **Actions** ← إن ظهرت رسالة تفعيل فاضغط تفعيل ← **Build Android APK** ← **Run workflow**. انتظر 10–25 دقيقة حتى ✅.
5. افتح التشغيل الناجح ← أسفل الصفحة **Artifacts** ← **smart-deals-apk** ← فك ضغط الملف ← انقل الـ APK لجوالك وثبّته (اسمح بالتثبيت من مصدر غير معروف).
6. إن ظهرت ❌: افتح خطوة **Build APK**، اكتب `error` في بحث السجل، وأرسل لي السطور.

## 6) النشر على Google Play
حساب مطوّر (رسوم لمرة واحدة) • سياسة خصوصية (`privacy_policy_template.md` وضع رابطها في الإعدادات) • Data safety: لا بيانات تُجمع • حزمة AAB موقّعة عبر `build_aab.yml` (لم أجربه).
