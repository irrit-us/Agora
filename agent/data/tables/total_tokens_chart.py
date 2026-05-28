import numpy as np
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt

# 设置字体为 Times New Roman
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman']

# 设置数据
ablations = ['Agora', 'w/o bug-explo', 'w/o state-ana', 
             'w/o constraints-ana', 'w/o scena-gen', 'w/o reflect-loop']
repos = ['Raft', 'EPaxos', 'HotStuff', 'Sui']

# ================================================================================
# 真实数据来源：agent/data/tables/data
# Total Tokens 数据
# ================================================================================

# Total Tokens 数据
# 顺序: [Agora, w/o bug-explo, w/o state-ana, w/o constraints-ana, w/o scena-gen, w/o reflect-loop]
total_tokens = {
    'Raft':     [5_127_864,   3_320_339,   16_190_118,  11_477_543,  18_394_970,  4_218_941],
    'EPaxos':   [22_948_326,  14_782_536,  28_156_840,  13_644_942,  87_412_641,  17_146_523],
    'HotStuff': [12_696_097,  8_414_564,   15_428_719,  6_732_950,   53_675_186,  9_653_814],
    'Sui':      [17_832_415,  17_250_732,  19_847_263,  9_748_327,   73_594_184,  15_892_470],
}

# 自定义配色
repo_colors = ['#FA7F6F', '#82B0D2', '#8ECFC9', '#FFBE7A']  # 红、蓝、绿、橙

# ==================== 柱状图 - Total Tokens ====================
fig, ax = plt.subplots(figsize=(32, 14))  # 更扁的尺寸
x = np.arange(len(ablations)) * 1.3  # 增加横坐标间距
width = 0.30  # 柱子宽度（更粗）
n_repos = len(repos)

for i, repo in enumerate(repos):
    offset = (i - n_repos/2 + 0.5) * width
    values = total_tokens[repo]
    
    # 绘制柱状图
    bars = ax.bar(
        x + offset, 
        values, 
        width,
        label=repo,
        color=repo_colors[i],
        edgecolor='white',
        linewidth=2
    )

ax.set_xticks(x)
ax.set_xticklabels(ablations, fontsize=76, rotation=15, ha='right')
ax.set_ylabel('Total Tokens', fontsize=72)
ax.tick_params(axis='y', labelsize=64)
ax.set_ylim(0, 100e6)  # 设置 y 轴范围，最大值约 90M
# 不显示图例
# 添加网格线
ax.yaxis.grid(True, linestyle='--', alpha=0.7)
ax.set_axisbelow(True)

# 设置 y 轴格式为百万
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1e6:.0f}M'))

plt.tight_layout()
fig.savefig('total_tokens.png', dpi=400, bbox_inches='tight')
print("图已保存为 total_tokens.png")
