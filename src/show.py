"""
让生成的过程可视化，可以选取哪部分用来可视化
"""

def print_save(result):
    # 处理结果
    print("*"*80)
    print("流程结束，处理结果")
    if result["result"] == "小说创作流程完成":
        outline = result['final_outline']
        character = result['final_characters']       
        content = result['final_content']
        
        print(f"\n小说创作流程完成! 共生成 {len(character)} 个章节")
        print("-" * 80)
        print(f"小说标题: {outline.title}")
        print(f"类型: {outline.genre}")
        print(f"主题: {outline.theme}")
        
        # 显示部分结果预览
        print("\n" + "-" * 40)
        print("角色档案预览 (前2个角色):")
        print("-" * 40)
        for char in character[:2]:
            print(f"\n角色名称: {char.name}")
            print(f"性格: {char.personality}")
            print(f"目标: {', '.join(char.goals)}")

        # 显示章节内容预览
        print("\n" + "-" * 40)
        print("章节内容预览 (前2章):")
        print("-" * 40)
        for i, chapter in enumerate(content[:2], 1):
            print(f"\n第{i}章: {chapter.title}")
            print("-" * 30)
            preview = chapter.content
            print(preview)
            
        if len(content) > 2:
            print(f"\n... 还有 {len(result['chapters_content']) - 2} 章未显示")
                
        # 提示保存选项
        print("\n" + "-" * 80)
        save_option = input("是否要将完整内容保存到文件? (y/n): ")
        if save_option.lower() == 'y':
            filename = f"{outline.title.replace(' ', '_')}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"小说标题: {outline.title}\n")
                f.write(f"类型: {outline.genre}\n")
                f.write(f"主题: {outline.theme}\n")
                f.write(f"背景: {outline.setting}\n\n")
                f.write("情节概要:\n")
                f.write(f"{outline.plot_summary}\n\n")
                    
                f.write("角色档案:\n")
                for char in character:
                    f.write(f"角色名称: {char.name}\n")
                    f.write(f"背景: {char.background}\n")
                    f.write(f"性格: {char.personality}\n")
                    f.write(f"目标: {', '.join(char.goals)}\n")
                    f.write(f"冲突: {', '.join(char.conflicts)}\n")
                    f.write(f"成长弧线: {char.arc}\n\n")
                    
                f.write("章节内容:\n")
                for i, chapter in enumerate(content, 1):
                    f.write(f"第{i}章: {chapter.title}\n")
                    f.write(f"{chapter.content}\n\n")
                
            print(f"内容已保存到 {filename}")
    else:
        print(f"\n生成失败: {result['final_error']}")
