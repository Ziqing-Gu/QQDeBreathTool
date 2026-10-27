"""Build the illustrated standalone 1.12 manuals (ReportLab + pypdf)."""
from pathlib import Path
from xml.sax.saxutils import escape
import argparse, json, os
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether, Image, Table, TableStyle, Flowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader
ROOT=Path(__file__).parent
INK=colors.HexColor('#172B36');TEAL=colors.HexColor('#087E87');MUTED=colors.HexColor('#586B75');PALE=colors.HexColor('#ECF4F5');GOLD=colors.HexColor('#D7A047')
W,H=595.276,841.89;CW=W-92

PAGES=[
 dict(zh=['QQDeBreathTool','独立版 1.12 Stable · 图文使用说明','先找到呼吸，再决定保留多少。'],en=['QQDeBreathTool','Standalone 1.12 Stable · Illustrated user guide','Find the breaths. Decide how much to keep.'],image='overview.png',diagram='flow',sections=[
  ('适用范围','About this guide','用于 Windows x64、Apple Silicon 和 Intel Mac 的独立应用。操作在独立窗口中完成，结果导出为对齐的三条 WAV；不需要 ARA、VST3、AU 或宿主扫描。','For the Windows x64, Apple Silicon and Intel Mac standalone app. Work in its own window and export three aligned WAV stems. ARA, VST3, AU and DAW scanning are not involved.'),
  ('阅读路线','Reading map','安装与升级 02 / 导入与分析 03 / 区域编辑 04 / 试听与显示 05 / 淡化与呼吸音量 06 / 撤销与会话恢复 07 / 导出与排错 08。','Installation 02 / Import and analyze 03 / Edit regions 04 / Monitor and display 05 / Fades and breath level 06 / Undo and session restore 07 / Export and troubleshooting 08.'),
  ('关于配图','About the illustrations','配图由 1.12 实际界面离屏渲染；使用生成的演示波形，区块为手工放置，不代表识别准确率。示例呼吸音量为 -6 dB，软件默认值是 0 dB。','Screenshots render the actual 1.12 interface offscreen with generated audio and manually placed regions; they are not detection-accuracy evidence. The example uses -6 dB Breath Gain; the default is 0 dB.')]),
 dict(zh=['02 / 安装与升级','完整复制程序目录，保留原始素材与用户设置。',''],en=['02 / Install and upgrade','Keep the complete app together, with original audio and settings intact.',''],diagram='platform',sections=[
  ('Windows：解压后直接运行','Windows: extract and run','选择 Windows-x64 压缩包。退出旧程序，保留旧版副本，再解压并放好整个 QQDeBreathTool 文件夹；双击 QQDeBreathTool.exe。_internal 是必要运行库，不能省略，也不要把新旧运行库混在一起。无需安装 Python。适用于 Windows 10/11 x64。','Choose Windows-x64. Quit the old app and keep an old copy, then extract the complete QQDeBreathTool folder. Run QQDeBreathTool.exe. The _internal directory is required; do not copy the EXE alone or mix old and new runtime files. Python is not needed. Intended for Windows 10/11 x64.'),
  ('Mac：按芯片选择一个包','Mac: choose the matching chip','M 系列芯片选 Apple-Silicon；Intel 芯片选 Intel。使用 Mac 系统归档实用工具解压，把 QQDeBreathTool.app 复制到“应用程序”，替换旧 APP。不要先在 Windows 解压再传回 Mac；这样可能丢失符号链接或执行权限。最低系统版本见本次 Release 与安装说明。','Choose Apple-Silicon for M-series chips, or Intel for Intel Macs. Extract with Archive Utility and copy QQDeBreathTool.app to Applications, replacing the old app. Do not unpack on Windows first: symbolic links or executable permissions may be lost. See the release and installation guide for the verified minimum macOS version.'),
  ('Mac 首次打开','First launch on Mac','Mac 成品使用 ad-hoc 签名，未做 Developer ID 公证。确认来自正式仓库后，可尝试右键“打开”或系统设置的“隐私与安全性”。若确为隔离属性拦截，安装说明提供仅针对该可信 APP 的处理方法。','Mac builds are ad-hoc signed, without Developer ID notarization. After verifying the official source, use right-click Open or Privacy & Security if needed. The installation guide gives an app-specific quarantine remedy when that is the cause.'),
  ('下载入口','Official downloads','github.com/Ziqing-Gu/QQDeBreathTool/releases/tag/v1.12。下载可运行的平台包；Complete-Source.zip 和 GitHub 的 Source code 是源码，不是安装程序。','github.com/Ziqing-Gu/QQDeBreathTool/releases/tag/v1.12. Download the runnable package for your platform. Complete-Source.zip and GitHub Source code downloads are source, not apps.')]),
 dict(zh=['03 / 导入与自动分析','自动分析识别 Breath；Noise 留给你手动判断。',''],en=['03 / Import and analyze','Automatic analysis finds Breath. Mark Noise manually.',''],image='editing-toolbar.png',sections=[
  ('1. 打开一份人声素材','1. Open a vocal recording','点击“打开/拖入音频”，或把文件拖进窗口。支持 WAV、AIF/AIFF、FLAC、OGG、MP3 等；具体解码取决于格式编码。读取后查看底部采样率、声道数与时长。读取失败时可先转为标准 PCM WAV。','Click 打开/拖入音频 (Open / Drop Audio), or drag a file into the window. WAV, AIF/AIFF, FLAC, OGG and MP3 are offered; decoding depends on the file encoding. Check the sample rate, channel count and duration at the bottom. Convert unsupported material to PCM WAV if needed.'),
  ('2. 点击蓝色“分析”','2. Click 分析 (Analyze)','分析对象是当前载入的整份音频，缩放视图不会缩短分析范围。进度窗口显示处理状态，等待完成后再编辑。当前界面没有分析取消按钮，也没有可调检测阈值。','Analysis covers the entire loaded file; zooming the waveform does not restrict its range. Wait for the progress window to finish before editing. This interface has no analysis-cancel button or adjustable detection-threshold control.'),
  ('3. 检查蓝色呼吸区块','3. Review the blue regions','蓝色为 Breath，黄色为 Noise，没有标记的部分归入 Vocal Only。自动结果只给出 Breath；短辅音、气声尾音可能需要人工纠正。不要仅凭波形颜色决定删掉什么，先试听。','Blue marks Breath and amber marks Noise. Unmarked audio belongs to Vocal Only. Automatic results identify Breath only; consonants and breathy word tails may need correction. Audition before deciding what to remove.'),
  ('重复分析与速度','Reanalysis and speed','再次点击“分析”会用新结果替换当前区块；同一会话内可用 Undo 恢复。1.12 优化运算并减少纯零窗口开销；长文件不一定都能同幅提速。Windows 样本测验中部分素材由约 25-43 秒降至约 5-9 秒；这些不是 Mac 测速结果。','Analyzing again replaces the current regions; Undo can restore them within the current session. Version 1.12 reduces repeated computation and exact-zero window work, but gains vary. Some Windows recordings improved from about 25-43 seconds to 5-9 seconds; those figures are not Mac benchmarks.')]),
 dict(zh=['04 / 修正、补画与删除','放大边界，保留字头与字尾。',''],en=['04 / Correct the regions','Zoom in and preserve the start and end of each word.',''],image='breath-closeup.png',imageHeight=185,diagram='edit',sections=[
  ('选择与边界','Select and adjust','单击区块选中；拖动左右边缘改变起止位置，拖动中间移动整个区块。白色边框表示当前选择。底部区块时码可双击或右键复制，便于记录需要复查的位置。','Click a region to select it. Drag its left or right edge to change the boundary; drag the middle to move the whole region. A white border shows selection. Double-click or right-click the region timecode at the bottom to copy it for review notes.'),
  ('补画、改类型与删除','Create, reclassify and delete','先在“类型”选择 Breath 或 Noise，再按住 Shift 拖动画出新区块。选中后按 B 设为 Breath，按 N 设为 Noise；右键区块在两类间切换。按 Delete 或“删除区块”移除标记；该声音重新归入 Vocal Only，并不是从原文件剪掉。','Choose Breath or Noise in 类型 (Type), then Shift-drag to draw a region. With a region selected, B assigns Breath and N assigns Noise; right-click toggles the two types. Delete or 删除区块 removes the marking, returning that audio to Vocal Only. It does not cut samples from the original file.'),
  ('缩放与定位','Zoom and navigate','滚轮在鼠标附近缩放；Shift+滚轮左右移动，也可拖底部滚动条。点击“全览”显示完整音频。左键点击波形还会设置播放位置；编辑前先把要处理的呼吸放大。','Use the wheel to zoom around the pointer. Shift-wheel pans horizontally; the bottom scrollbar also moves the view. 全览 (Fit) shows the full file. Left-clicking the waveform also sets the playhead. Zoom into a breath before editing its edges.')]),
 dict(zh=['05 / 试听与波形显示','监听选择、显示倍率和导出处理是不同的控制。',''],en=['05 / Monitor and display','Listening selection, display scale and exported processing have different roles.',''],image='transport.png',secondImage='breath-solo.png',secondHeight=180,sections=[
  ('先单听，再合听','Solo first, then combine','Monitor 下的 Voice、Breath、Noise 可任意组合。先只勾 Breath，检查是否混入歌词；再只勾 Voice，检查字头字尾是否完整；最后合听。勾选状态也决定哪些分轨显示波形；全部取消会静音。','Combine Voice, Breath and Noise freely under Monitor. Listen to Breath alone to catch words inside the regions, then Voice alone to check word edges, then the combined result. The checkboxes also control which stem waveforms are displayed. Unchecking all three produces silence.'),
  ('播放、跟随与回起点','Playback, follow and return','点击“播放”或按空格切换播放状态；“停止”结束播放。“跟随”让视图随播放位置翻动；“回起点”启用时，停止或自然结束会按程序的播放起点逻辑返回。','Click 播放 (Play) or press Space to toggle playback; 停止 (Stop) ends it. 跟随 (Follow) scrolls the view with playback. 回起点 (Return to start) returns to the playback start when stopping or reaching the end, according to the app transport behavior.'),
  ('两个容易混淆的数值','Two easy-to-confuse controls','“显示”0.1-64 倍只改变波形视觉高度，不改变声音。“监听”-20 至 +20 dB 只影响播放音量，不写入导出文件。Monitor 勾选也不会决定是否导出对应轨；“导出三轨”始终输出三份。','显示 (Display), 0.1-64x, changes only waveform height. 监听 (Monitor Gain), -20 to +20 dB, affects listening volume only, not exported files. Monitor checkboxes do not select which stems are exported: Export Three Stems always writes all three.')]),
 dict(zh=['06 / 淡化与呼吸音量','这些处理会影响试听及导出的呼吸轨。',''],en=['06 / Fades and breath level','These controls shape monitoring and exported stems.',''],image='processing-toolbar.png',diagram='processing',sections=[
  ('Fade：处理区块交接处','Fade: smooth the boundaries','启用 Fade 后，In / Out 控制全局淡入、淡出，范围各为 0-500 ms，默认各 10 ms。它们不是某个选中区块专属参数；相邻区块使用共享交叉淡化。先用短淡化，再试听是否误伤发音。','When Fade is enabled, In and Out set global fade-in and fade-out times: 0-500 ms each, default 10 ms each. They are not per-selected-region settings. Adjacent regions share a crossfade. Start with short fades and listen for affected word edges.'),
  ('呼吸标准化：按区块峰值调整','Normalize Breath: per-region peaks','勾选“呼吸标准化”，每个 Breath 区块的峰值会调整到“目标”电平；目标范围 -60 至 0 dB，默认 -6 dB。这是峰值标准化，不是 LUFS 匹配、压缩器或降噪。','呼吸标准化 (Normalize Breath) scales each Breath region to the 目标 (Target) peak level. Target ranges from -60 to 0 dB, default -6 dB. This is peak normalization, not LUFS matching, compression or noise reduction.'),
  ('呼吸音量：控制整体呼吸量','Breath Gain: set the overall breath level','“呼吸音量”范围 -30 至 +30 dB，默认 0 dB；标准化启用时，先标准化，再应用这个增益。降低它可保留呼吸节奏同时减轻存在感。较高的目标再叠加正增益可能导致削波，需结合电平表试听。','呼吸音量 (Breath Gain) ranges from -30 to +30 dB, default 0 dB. When normalization is on, gain follows normalization. Lower it to retain the breathing rhythm more subtly. A high target plus positive gain can clip; monitor the meter and listen.'),
  ('数值怎么调','Editing numeric values','上下拖动数值；Shift 配合拖动用于微调，Alt+左键恢复默认，双击可输入数值。示例图中的 -6 dB 是演示设置。Fade、标准化、目标和呼吸音量会影响导出；“监听”增益不会。','Drag numeric values up or down; Shift-drag provides fine adjustment, Alt-click resets the default, and double-click opens numeric entry. The pictured -6 dB is a demonstration setting. Fades, normalization, target and Breath Gain affect export; Monitor Gain does not.')]),
 dict(zh=['07 / 撤销、恢复与工作习惯','保存了编辑结果，不等于保存了完整撤销历史。',''],en=['07 / Undo and session restore','Restoring edits is different from restoring the undo history.',''],image='editing-toolbar.png',diagram='history',sections=[
  ('Undo / Redo 的范围','What Undo / Redo covers','独立版保留最多 100 步区块历史：分析、补画、移动、改边界、改类型和删除。点击 Undo / Redo，或在 Windows 用 Ctrl+Z / Ctrl+Shift+Z。Mac 可直接使用界面按钮，快捷键映射以系统实际行为为准。','The standalone app keeps up to 100 region-edit steps: analysis, creation, movement, boundary changes, type changes and deletion. Use the Undo / Redo buttons, or Ctrl+Z / Ctrl+Shift+Z on Windows. On Mac, the buttons are always the clearest route; key mapping follows platform behavior.'),
  ('参数没有纳入区块撤销','Parameters are outside region undo','Fade、呼吸标准化、目标、呼吸音量、监听勾选和监听增益不属于这个区块历史。不要期待一次 Undo 恢复这些参数；用数值输入或 Alt+左键恢复需要的值。','Fades, normalization, target, Breath Gain, monitor checkboxes and Monitor Gain are outside this region history. Undo does not restore those values; use numeric entry or Alt-click reset as appropriate.'),
  ('退出再打开会恢复什么','What returns after reopening','程序记住上次音频路径、该音频的编辑区块和常用处理/监听设置。原始文件必须仍在原位置。关闭后重启会自动恢复上次区块；手动重新打开音频或换文件会清空当前区块。以上操作都会清空 Undo / Redo；它不保存每份文件的独立历史。','The app remembers the last audio path, its edited regions and common processing/monitor settings. The original file must remain at that path. Relaunching restores the last regions automatically; manually opening or switching files clears the current regions. All these actions clear Undo / Redo. Separate per-file histories are not retained.'),
  ('推荐的收尾','A practical finish','调整满意后立即导出到新的文件夹，保留原始录音。重新分析前先确认当前编辑已不再需要，或准备在当前会话内 Undo。修改来源文件名或移动文件前，先完成导出。','When satisfied, export into a fresh folder and keep the original recording. Before reanalyzing, confirm whether you still need the current edits or be ready to Undo in the same session. Export before renaming or moving the source file.')]),
 dict(zh=['08 / 导出与排错','三轨保持原始时间位置，可直接放回宿主对齐。',''],en=['08 / Export and troubleshoot','All three stems retain their original timeline positions.',''],diagram='export',sections=[
  ('导出三轨','Export Three Stems','点击绿色“导出三轨”，选择输出文件夹。以 Vocal.wav 为例，输出 Vocal_Vocal Only.wav、Vocal_Breath.wav、Vocal_Noise.wav。三份都保留原音频的完整长度、采样率和声道数，方便从同一起点对齐。淡化与呼吸处理写入结果；它们与原音频简单相加不一定完全相同。','Click the green 导出三轨 (Export Three Stems) button and select a folder. Vocal.wav produces Vocal_Vocal Only.wav, Vocal_Breath.wav and Vocal_Noise.wav. Each retains the full duration, sample rate and channel count for alignment at the same start point. Fades and breath processing are rendered into the result, so summing the processed stems may differ from the original.'),
  ('避免覆盖与常见问题','Avoid overwrites and common issues','同一来源文件在同一目录再次导出，会写入同名文件。需要比较多个方案时选新的文件夹。没有声音：检查 Monitor 是否全关、监听音量和系统音频输出。呼吸误识别：改边界、改类型或删除标记，再试听。缺少文件/运行库：重新完整解压程序。','Exporting the same source to the same folder writes the same filenames again. Use a new folder for alternate versions. No sound: check Monitor selection, Monitor Gain and system output. Wrong detection: adjust boundaries, change the type or delete the marking and audition again. Missing runtime/model: extract the complete app package again.'),
  ('1.12 的验证范围','What was verified for 1.12','Windows 的八份原始音频检测区域与 1.11 一致；合成数据、浮点状态恢复、离屏界面分析与撤销重做、打包 EXE 分析均通过。Mac 构建与自动检查见本版 Release；这不代表已完成真实 Mac 桌面试听验收。','Windows detection regions matched 1.11 on eight original recordings. Synthetic cases, floating-point restoration, offscreen GUI analysis/Undo/Redo and packaged EXE analysis passed. Mac build and automated-check results are in the release. These are not claims of real Mac desktop listening acceptance.'),
  ('许可、反馈与归属','License, feedback and credits','顾子青 / Qing Audio。沿用 Qing Audio 非商业源码共享许可证 1.0，禁止商业使用；分发须免费公开完整对应源码、保留署名及许可、注明来源与修改并沿用同一许可证。第三方库保留各自许可。反馈请带上 1.12、系统与芯片、复现步骤及可分享的最短素材。QQ 群：692973169。','Gu Ziqing / Qing Audio. Qing Audio Non-Commercial Source-Share License 1.0 applies: NO COMMERCIAL USE. Distribution requires complete corresponding source at no charge, attribution and notices, stated origin/changes and the same license. Third-party licenses remain applicable. For feedback, include version 1.12, OS/chip, reproduction steps and a short shareable sample. QQ group: 692973169.')])
]

class Diagram(Flowable):
    def __init__(self,kind,zh): super().__init__();self.kind=kind;self.zh=zh;self.width=CW;self.height=77
    def draw(self):
        c=self.canv;c.setFillColor(PALE);c.roundRect(0,0,CW,72,7,fill=1,stroke=0)
        z=self.zh
        labels={
          'flow':(['导入','分析','修正','试听','导出'] if z else ['Import','Analyze','Edit','Listen','Export']),
          'platform':['Windows x64','Apple Silicon','Intel Mac'],
          'edit':(['左边缘：起点','中间：移动','右边缘：终点'] if z else ['Left: start','Middle: move','Right: end']),
          'processing':(['Fade','峰值标准化','呼吸音量'] if z else ['Fade','Peak normalize','Breath Gain']),
          'history':(['当前区块','Undo / Redo','关闭：历史清空'] if z else ['Current regions','Undo / Redo','Close: history clears']),
          'export':['Vocal Only.wav','Breath.wav','Noise.wav']}[self.kind]
        step=(CW-22)/len(labels)
        for i,s in enumerate(labels):
            x=11+i*step;c.setFillColor(TEAL if i%2==0 else INK);c.roundRect(x,21,step-12,31,4,fill=1,stroke=0)
            c.setFont('CJK',9 if self.kind=='history' else 9.5);c.setFillColor(colors.white);c.drawCentredString(x+(step-12)/2,32,s)
            if i<len(labels)-1 and self.kind in ('flow','processing','history'):c.setFillColor(TEAL);c.drawCentredString(x+step-6,32,'>')

def build(lang):
    zh=lang=='ZH-CN'
    st={
     'title':ParagraphStyle('title',fontName='CJKB',fontSize=27,leading=36,textColor=INK,spaceAfter=8),
     'deck':ParagraphStyle('deck',fontName='CJK',fontSize=11,leading=17,textColor=MUTED,spaceAfter=14),
     'head':ParagraphStyle('head',fontName='CJKB',fontSize=12,leading=18,textColor=TEAL,spaceBefore=10,spaceAfter=5),
     'body':ParagraphStyle('body',fontName='CJK',fontSize=10.1,leading=16.5,textColor=INK,spaceAfter=8,wordWrap='CJK' if zh else None),
     'caption':ParagraphStyle('caption',fontName='CJK',fontSize=8.2,leading=12,textColor=MUTED,spaceBefore=5,spaceAfter=9),
    }
    target=ROOT/f'QQDeBreathTool-1.12-User-Manual-{lang}.pdf'
    def chrome(c,d):
        c.setTitle('QQDeBreathTool 1.12 - '+('独立版图文说明书' if zh else 'Illustrated Standalone User Guide'));c.setAuthor('Qing Audio / Gu Ziqing')
        c.setStrokeColor(TEAL);c.setLineWidth(2);c.line(46,H-43,W-46,H-43)
        c.setFont('Helvetica-Bold',9);c.setFillColor(TEAL);c.drawString(46,H-31,'QING AUDIO / QQDeBreathTool')
        c.setFont('Helvetica',8);c.setFillColor(MUTED);c.drawRightString(W-46,H-31,'STANDALONE 1.12 STABLE')
        c.setStrokeColor(colors.HexColor('#CCDADB'));c.setLineWidth(.4);c.line(46,40,W-46,40)
        c.setFont('CJK',8);c.drawString(46,25,'2026-10-27 | '+('独立应用 · 图文版' if zh else 'Standalone app / Illustrated edition'));c.drawRightString(W-46,25,f'{d.page} / 8')
        c.linkURL('https://github.com/Ziqing-Gu/QQDeBreathTool/releases/tag/v1.12',(46,20,300,37),relative=0)
    story=[]
    for i,p in enumerate(PAGES):
        title,deck,sub=p['zh' if zh else 'en']
        story+=[Paragraph(escape(title),st['title']),Paragraph(escape(deck),st['deck'])]
        if sub:story.append(Paragraph(escape(sub),st['body']))
        if p.get('image'):
            img=Image(str(ROOT/'images'/p['image']));scale=CW/img.imageWidth
            height=min(p.get('imageHeight',235),img.imageHeight*scale)
            # Use proportional scaling only, never distort a screenshot.
            width=height*img.imageWidth/img.imageHeight
            story += [Image(str(ROOT/'images'/p['image']),width=width,height=height),Paragraph(('图 '+str(i+1)+' · 1.12 实际界面；演示波形与手工区块。' if zh else 'Figure '+str(i+1)+' · Actual 1.12 interface; generated audio and manually placed regions.'),st['caption'])]
        if p.get('secondImage'):
            img=Image(str(ROOT/'images'/p['secondImage']));height=p['secondHeight'];story += [Image(str(ROOT/'images'/p['secondImage']),width=height*img.imageWidth/img.imageHeight,height=height),Spacer(1,7)]
        if p.get('diagram'):story += [Diagram(p['diagram'],zh),Spacer(1,4)]
        for hz,he,bz,be in p['sections']:
            story += [KeepTogether([Paragraph(escape(hz if zh else he),st['head']),Paragraph(escape(bz if zh else be),st['body'])])]
        if i<7:story.append(PageBreak())
    doc=SimpleDocTemplate(str(target),pagesize=(W,H),leftMargin=46,rightMargin=46,topMargin=65,bottomMargin=53)
    doc.build(story,onFirstPage=chrome,onLaterPages=chrome)
    reader=PdfReader(target)
    assert len(reader.pages)==8,(lang,len(reader.pages))
    assert all(len(p.extract_text())>180 for p in reader.pages)
    return dict(language=lang,pages=len(reader.pages),path=str(target),bytes=target.stat().st_size)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--font-regular',default=str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/msyh.ttc'));p.add_argument('--font-bold',default=str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/msyhbd.ttc'));args=p.parse_args()
    pdfmetrics.registerFont(TTFont('CJK',args.font_regular,subfontIndex=0));pdfmetrics.registerFont(TTFont('CJKB',args.font_bold,subfontIndex=0))
    print(json.dumps([build('ZH-CN'),build('EN')],ensure_ascii=False,indent=2))
