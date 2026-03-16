# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置文件
使用方法: pyinstaller hw_datasheet_agent.spec
"""

block_cipher = None

a = Analysis(
    ['hw_datasheet_agent.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 配置文件模板（打包到 exe 内部作为默认模板）
        ('config.yaml.example', '.'),
    ],
    hiddenimports=[
        # LangChain 相关
        'langchain',
        'langchain_openai',
        'langchain_community',
        'langchain_text_splitters',
        # 文档加载器
        'pymupdf',
        'docx',
        'docx2txt',
        # 数据处理
        'pandas',
        'openpyxl',
        # Token 计数
        'tiktoken',
        'tiktoken_ext',
        'tiktoken_ext.openai_public',
        # 配置和日志
        'yaml',
        'tqdm',
        # Agent 模块
        'agent',
        'agent.state_manager',
        'agent.core_agent',
        'reviewer',
        'reviewer.data_reviewer',
        'reviewer.audit_report',
        'reviewer.checks',
        'reviewer.checks.base',
        'reviewer.checks.structure_check',
        'reviewer.checks.table_check',
        'reviewer.checks.data_consistency_check',
        'config',
        'config.constants',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型库以减小体积
        'matplotlib',
        'numpy.f2py',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='hw_datasheet_agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # 使用 UPX 压缩减小体积
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 保持控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标: icon='icon.ico'
)
