# 素材与展示依据

新增片头沿用原有 LUMIX SVG；lumix-letter-mask.svg 只去除其背景矩形以便作为玻璃渐变蒙版，字形和下划线未重新绘制。glass-grain.svg 是固定种子的细微磨砂纹理。feature-first-frame.png 从已交付视频首帧提取，仅用于片头接入原片时匹配画面。

软件为洗衣机管理器 0.7，所有界面取自实际运行的 Python/pywebview 程序；源参考为 ../photo-manager/pianji/ui，色彩 #151618 / #202124 / #e9c084 / #f4f4f6。LUMIX 字标沿用用户既有软件图标文件，未重画。

materials/ui/*.html 是实际运行状态的 DOM 快照，保留软件的真实文案、图标、布局与数据。materials/*.png 为对应窗口参考图。文件位置和本机账户路径均已脱敏；演示来源只有下列公开照片，不使用用户 SD 卡照片。自动人物分组真实运行本地 YuNet/SFace 得到 3 个普通人物与 1 张待分类。

关联 RAW/JPEG 一镜属于影片中的关系图解，以同一照片连接两个文件类型，并非伪造软件实际的 RAW 解码结果。Photoshop 设置展示真实的自定义路径入口，不宣称已启动 Photoshop 或自动完成修图。成片镜头由实际“标为成片”与关联机制产生，示例 JPEG 为已完成的公开作品。

## 照片

均为项目已有 Unsplash 示例照片，已核对各照片页的免费使用标识及 https://unsplash.com/license 。不暗示照片人物或摄影师认可本软件。

- a.jpg — Punto Fotográfico：https://unsplash.com/photos/a-woman-dressed-in-a-cosplay-costume-EVD18HpSOig
- b.jpg — Sou Jest：https://unsplash.com/photos/blonde-woman-in-black-cosplay-costume-looking-at-camera-a1jZlq_ggKM
- c.jpg — Fikri Ali Kurnia：https://unsplash.com/photos/woman-in-costume-with-blonde-wig-and-bow-ABoHCuDGHBE
- d.jpg — Bryan Turner：https://unsplash.com/photos/woman-with-cosplay-costume-holding-swor-bV11km8xYlA

## 字体与声音

影片中文使用本地随工程提供的 Noto Sans SC 500；英文/数字用 Inter 可变字体，许可证见 assets/fonts/。真实 UI 快照保留软件 Windows 系统字体（不打包微软字体文件）。用户要求无音乐；本片默认无旁白、无音轨。

huashu-motion 本机 CLI 0.1.1 不提供 grab 命令，已使用实际程序采集替代；其余 check/still/render/qa/studio 流程照常执行。软件不因制作本视频而修改。
