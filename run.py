from pathlib import Path
import sys

def main():
    if len(sys.argv)>1 and sys.argv[1]=='--self-test':
        from pianji.selftest import run
        return run(Path(sys.argv[2]))
    from pianji.app import start
    start()
    return 0

if __name__=='__main__':
    try: sys.exit(main())
    except Exception:
        import traceback,os
        details=traceback.format_exc()
        root=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Pianji';root.mkdir(parents=True,exist_ok=True)
        (root/'startup-error.log').write_text(details,encoding='utf-8')
        if sys.platform=='win32':
            import ctypes
            reason=str(sys.exc_info()[1])
            ctypes.windll.user32.MessageBoxW(None,'片集启动失败：'+reason+'\n\n请完整解压程序文件夹；WebView2错误需安装 Microsoft Edge WebView2 Runtime。\n错误记录：'+str(root/'startup-error.log'),'片集',0x10)
        else: print(details,file=sys.stderr)
        sys.exit(1)
