# MAYHEM LAB · 海克斯大乱斗网页

Vue 3 + Vite 单页应用。数据是静态 JSON，不需要后端。

## 开发

从仓库根目录：

```bash
cd web
npm install
npm run dev
```

打开 `http://127.0.0.1:5178/`。

## 重新生成数据

```bash
python3 scripts/export_web.py
```

会写入 `web/public/data/lol.json`（约 8 MB）。

## 构建

```bash
npm run build
```

产物在 `web/dist/`，可直接用任意静态服务器托管。
