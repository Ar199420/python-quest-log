# Python Quest Log (RPG Style)

Tracker belajar Python bergaya RPG. Jalan di Termux, murni Python stdlib (tanpa install apa-apa lagi).

## Cara pakai

```bash
# 1. init sekali di awal
python3 quest_log.py init

# 2. lihat daftar quest
python3 quest_log.py list

# 3. lihat hint (deskripsi skill, bukan tutorial penuh)
python3 quest_log.py hint 1

# 4. tandai mulai
python3 quest_log.py start 1

# 5. setelah kamu berhasil praktik sendiri, tandai selesai -> dapat XP + auto git commit
python3 quest_log.py complete 1

# 6. cek karakter sheet kapan saja
python3 quest_log.py status
```

## Alur belajar yang disarankan (biar konsisten sama gaya main Persona Q2 kamu)

1. `hint <id>` — baca sekali, jangan overthink.
2. Buka Neovim, buat file baru misal `quest_01.py`, coba langsung praktik.
3. Kalau stuck lebih dari ~10-15 menit, baru cari referensi tambahan (bukan tutorial video panjang, cukup dokumentasi resmi Python atau `help()`).
4. Kalau sudah jalan dan kamu paham *kenapa* jalan (bukan cuma copy-paste), `complete <id>`.
5. Lanjut quest berikutnya.

## Alias biar cepat (opsional)

Tambahkan ke `~/.bashrc` atau `~/.zshrc` di Termux:

```bash
alias quest="python3 ~/questlog/quest_log.py"
```

Lalu tinggal ketik `quest list`, `quest hint 3`, dst dari mana saja.

## Integrasi GitHub (RPG style)

Repo ini didesain supaya commit = "battle log":

- Setiap `complete <id>` otomatis bikin commit dengan format:
  `feat(lvl{level}): unlock {nama quest}`
- README ini auto-update bagian **Character Sheet** di bawah setiap kali quest selesai, jadi kalau kamu push ke GitHub, profil repo-mu langsung kelihatan progress levelnya seperti status karakter.
- Saran: push repo ini ke GitHub sebagai `python-quest-log`, dan pin repo-nya — jadi tiap orang yang buka profil GitHub-mu lihat "character sheet" progres belajarmu.

Setup remote (sekali saja):

```bash
git init
git add -A
git commit -m "init: quest log dimulai"
git branch -M main
git remote add origin https://github.com/USERNAME/python-quest-log.git
git push -u origin main
```

Setelah itu, tiap `complete` akan auto-commit lokal. Kamu tinggal `git push` kapan-kapan mau sync ke GitHub.

---

<!-- CHARACTER_SHEET_START -->
## Character Sheet

- **Level:** 1
- **XP:** 20
- **Progress:** 1/13 quest selesai

**Skill dikuasai:**
- [x] Variabel & Tipe Data (Rank F)
<!-- CHARACTER_SHEET_END -->
