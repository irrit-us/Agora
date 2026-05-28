import numpy as np
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt

# 设置数据
ablations = ['Agora', 'w/o bug-explo', 'w/o state-ana', 
             'w/o constraints-ana', 'w/o scena-gen', 'w/o reflect-loop']
repos = ['Raft', 'EPaxos', 'HotStuff', 'Bullshark']

# ================================================================================
# 真实数据来源：agent/data/tables/data
# xxx 表示 0 bugs，无法计算 tokens/bug，用 None 表示
# ~ 开头的数值表示推断值
# ================================================================================

# Bugs Found 数据
bugs_found = {
    # 顺序: [Agora, w/o bug-explo, w/o state-ana, w/o constraints-ana, w/o scena-gen, w/o reflect-loop]
    'Raft':      [1, 0, 0, 1, 0, 0],
    'EPaxos':    [9, 0, 0, 1, 0, 0],
    'HotStuff':  [4, 3, 0, 0, 0, 0],
    'Bullshark': [1, 0, 0, 0, 0, 0],
}

# bugs/hour 数据（所有实验运行3小时，bugs_per_hour = bugs_found / 3）
RUN_HOURS = 3
bugs_per_hour = {
    ablation: [bugs_found[repo][i] / RUN_HOURS for repo in repos]
    for i, ablation in enumerate(ablations)
}

# 为6个ablation配置分配颜色
cmap = plt.get_cmap('tab10')
ablation_colors = [cmap(i) for i in range(6)]

# ==================== 折线图 - Bugs per Hour ====================
fig2, ax2 = plt.subplots(figsize=(12, 8))
x2 = np.arange(len(repos))
markers = ['o', 's', '^', 'D', 'v', 'p']

for i, ablation in enumerate(ablations):
    ax2.plot(
        x2, 
        bugs_per_hour[ablation], 
        marker=markers[i], 
        linestyle='-', 
        color=ablation_colors[i], 
        linewidth=2, 
        markersize=13,
        label=ablation
    )

ax2.set_xticks(x2)
ax2.set_xticklabels(repos, fontsize=17)
ax2.set_ylabel('Bugs/Hour', fontdict={'size': 18})
ax2.set_xlabel('Protocol', fontdict={'size': 18})
ax2.tick_params(axis='y', labelsize=16)
ax2.legend(fontsize=13, loc='upper right', ncol=2)

# 添加网格线
ax2.yaxis.grid(True, linestyle='--', alpha=0.7)
ax2.set_axisbelow(True)

# 设置 y 轴为整数
ax2.yaxis.set_major_locator(plt.MaxNLocator(integer=True))

plt.tight_layout()
fig2.savefig('bugs_per_hour.png', dpi=150, bbox_inches='tight')
print("图已保存为 bugs_per_hour.png")
