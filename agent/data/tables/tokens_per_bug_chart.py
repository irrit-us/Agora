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
repos = ['Raft', 'EPaxos', 'HotStuff', 'Bullshark']

# ================================================================================
# 真实数据来源：agent/data/tables/data
# xxx 表示 0 bugs，无法计算 tokens/bug，用 None 表示
# ================================================================================

# Tokens/Bug 数据 (None 表示 xxx，即 0 bugs 无法计算)
tokens_per_bug = {
    # 顺序: [Agora, w/o bug-explo, w/o state-ana, w/o constraints-ana, w/o scena-gen, w/o reflect-loop]
    # w/o constraints-ana: 只有 HotStuff 发现了 2 个 bug
    'Raft':      [5_127_864, None, None, None, None, None],
    'EPaxos':    [2_549_814, None, None, None, None, None],
    'HotStuff':  [3_174_024, 2_804_855, None, 3_366_475, None, None],
    'Bullshark': [17_832_415, None, None, None, None, None],
}

# 将 None 转为 0 用于绘图，并记录 None 位置用于标记 ×
def get_plot_data(data_dict):
    """返回可绘图数据和 None 位置标记"""
    plot_data = {}
    null_mask = {}
    for repo, values in data_dict.items():
        plot_data[repo] = [v if v is not None else 0 for v in values]
        null_mask[repo] = [v is None for v in values]
    return plot_data, null_mask

tokens_plot, tokens_null = get_plot_data(tokens_per_bug)

# 自定义配色
repo_colors = ['#FA7F6F', '#82B0D2', '#8ECFC9', '#FFBE7A']  # 红、蓝、绿、橙
# 纹理样式 - 不同的 hatch 图案（稀疏）
repo_hatches = ['/', 'x', '\\', '+']

# ==================== 柱状图 - Tokens/Bug ====================
fig, ax = plt.subplots(figsize=(32, 14))  # 更扁的尺寸
x = np.arange(len(ablations)) * 1.3  # 增加横坐标间距
width = 0.30  # 柱子宽度（更粗）
n_repos = len(repos)

# 用于记录 None 值位置，后续添加 × 标记
null_positions = []

for i, repo in enumerate(repos):
    offset = (i - n_repos/2 + 0.5) * width
    values = tokens_plot[repo]
    
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
    
    # 记录 None 位置用于添加 × 标记
    for j, is_null in enumerate(tokens_null[repo]):
        if is_null:
            null_positions.append((x[j] + offset, 0))

# 在 None 位置添加 × 标记
for pos_x, pos_y in null_positions:
    ax.scatter(pos_x, pos_y + 0.5e6, marker='x', color='#666666', s=1200, zorder=5, linewidths=8)

ax.set_xticks(x)
ax.set_xticklabels(ablations, fontsize=76, rotation=15, ha='right')
ax.set_ylabel('Tokens/Bug', fontsize=72)
ax.tick_params(axis='y', labelsize=64)
ax.set_ylim(0, 20e6)  # 缩小 y 轴范围，让柱子显得更高
ax.legend(fontsize=70, loc='upper right')

# 添加网格线
ax.yaxis.grid(True, linestyle='--', alpha=0.7)
ax.set_axisbelow(True)

# 设置 y 轴格式为百万
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1e6:.1f}M'))

plt.tight_layout()
fig.savefig('tokens_per_bug.png', dpi=400, bbox_inches='tight')
print("图已保存为 tokens_per_bug.png")
