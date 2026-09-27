import os

iconos_dir = r"c:\Ragnarok\interfaz\iconos"

# 1. YOUTUBE: Official Red box (#FF0000) with solid white triangle (#FFFFFF)
youtube_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <path fill="#FF0000" d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814z"/>
  <polygon fill="#FFFFFF" points="9.545,15.568 15.818,12 9.545,8.432"/>
</svg>'''

# 2. FACEBOOK: Official Blue circle (#1877F2) with solid white 'f' (#FFFFFF)
facebook_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <path fill="#1877F2" d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
  <path fill="#FFFFFF" d="M16.5 12.073h-3.328v-2.25c0-.949.465-1.874 1.956-1.874h1.564V4.996s-1.374-.235-2.686-.235c-2.741 0-4.533 1.662-4.533 4.669v2.643H6.426v3.47h3.047v8.385c.613.096 1.24.148 1.875.148.635 0 1.262-.052 1.875-.148v-8.385h2.796l.481-3.47z"/>
</svg>'''

# 3. TELEGRAM: Official circular gradient (#2AABEE -> #229ED9) with white airplane (#FFFFFF)
telegram_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <defs>
    <linearGradient id="tg-grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2AABEE"/>
      <stop offset="100%" stop-color="#229ED9"/>
    </linearGradient>
  </defs>
  <circle cx="12" cy="12" r="12" fill="url(#tg-grad)"/>
  <path fill="#FFFFFF" d="M5.4 11.9c3.9-1.7 6.5-2.8 7.8-3.4 3.7-1.5 4.5-1.8 5-.18.11.02.36.08.52.24.14.13.18.31.2.44.02.13.04.42.02.65-.25 2.65-1.33 9.06-1.88 12-.23 1.25-.7 1.67-1.14 1.71-.97.09-1.71-.64-2.65-1.26-1.47-.96-2.3-1.56-3.72-2.5-1.64-1.08-.58-1.67.36-2.65.25-.26 4.52-4.14 4.6-4.49.01-.04.02-.2-.07-.28-.09-.08-.23-.05-.33-.03-.14.03-2.42 1.54-6.84 4.52-.65.45-1.23.66-1.76.65-.58-.01-1.69-.33-2.52-.6-.94-.3-1.69-.47-1.62-.99.03-.27.42-.55 1.15-.84z"/>
</svg>'''

# 4. INSTAGRAM: Official gradient background with white camera outline (#FFFFFF)
instagram_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <defs>
    <radialGradient id="ig-grad" cx="20%" cy="110%" r="130%">
      <stop offset="0%" stop-color="#FFDD55"/>
      <stop offset="25%" stop-color="#FF543E"/>
      <stop offset="50%" stop-color="#C837AB"/>
      <stop offset="100%" stop-color="#3771C8"/>
    </radialGradient>
  </defs>
  <rect width="24" height="24" rx="6.5" fill="url(#ig-grad)"/>
  <rect x="3.5" y="3.5" width="17" height="17" rx="4.8" fill="none" stroke="#FFFFFF" stroke-width="1.8"/>
  <circle cx="12" cy="12" r="4.2" fill="none" stroke="#FFFFFF" stroke-width="1.8"/>
  <circle cx="16.8" cy="7.2" r="1.1" fill="#FFFFFF"/>
</svg>'''

# 5. TIKTOK: Official multi-color 3D chromatic glitch note (cyan #25F4EE, magenta #FE2C55, white #FFFFFF)
tiktok_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <rect width="24" height="24" rx="5" fill="#010101"/>
  <path fill="#25F4EE" d="M12.3 3.5v11.1a3.6 3.6 0 1 1-3.6-3.6c.3 0 .7.1 1 .2V7.7a7.2 7.2 0 1 0 6.2 7.1V8.6a8.8 8.8 0 0 0 4.6 1.3V6.3a5.2 5.2 0 0 1-4.6-2.8h-3.6z"/>
  <path fill="#FE2C55" d="M12.7 3.9v11.1a3.6 3.6 0 1 1-3.6-3.6c.3 0 .7.1 1 .2V8.1a7.2 7.2 0 1 0 6.2 7.1V9a8.8 8.8 0 0 0 4.6 1.3V6.7a5.2 5.2 0 0 1-4.6-2.8h-3.6z"/>
  <path fill="#FFFFFF" d="M12.5 3.7v11.1a3.6 3.6 0 1 1-3.6-3.6c.3 0 .7.1 1 .2V7.9a7.2 7.2 0 1 0 6.2 7.1V8.8a8.8 8.8 0 0 0 4.6 1.3V6.5a5.2 5.2 0 0 1-4.6-2.8h-3.6z"/>
</svg>'''

files = {
    "youtube.svg": youtube_svg,
    "facebook.svg": facebook_svg,
    "telegram.svg": telegram_svg,
    "instagram.svg": instagram_svg,
    "tiktok.svg": tiktok_svg
}

for name, content in files.items():
    p = os.path.join(iconos_dir, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content.strip())
    print(f"Saved {name} ({len(content)} bytes)")
