import shutil
from pathlib import Path

def move_files_auto_create_dir(source_path, dest_path, keyword):
    source_dir = Path(source_path)
    dest_dir = Path(dest_path)

    # 1. 元フォルダが存在するか確認 (念のための安全策)
    if not source_dir.exists():
        print(f"エラー: 元のフォルダが見つかりません -> {source_dir}")
        return

    # 2. 移動先フォルダが存在しない場合、自動的に作成する
    # parents=True: 親フォルダも一緒に作成 (例: ./a/b/c で aやbが無くても作る)
    # exist_ok=True: 既にフォルダがあってもエラーにしない
    if not dest_dir.exists():
        dest_dir.mkdir(parents=True, exist_ok=True)
        print(f"新規フォルダを作成しました: {dest_dir}")

    moved_count = 0
    skipped_count = 0

    print(f"--- 処理開始: '{source_dir}' から '{dest_dir}' へ ---")

    for item in source_dir.iterdir():
        # ファイルであり、かつキーワードが含まれているか
        if item.is_file() and keyword in item.name:
            destination_file = dest_dir / item.name

            # 3. 移動先に同名ファイルがある場合はスキップ
            if destination_file.exists():
                print(f"スキップ (同名ファイルあり): {item.name}")
                skipped_count += 1
            else:
                try:
                    shutil.move(str(item), str(destination_file))
                    print(f"移動完了: {item.name}")
                    moved_count += 1
                except Exception as e:
                    print(f"移動エラー ({item.name}): {e}")

    print("------------------------------------------------")
    print(f"処理終了: {moved_count} 件移動, {skipped_count} 件スキップ")

# --- 設定項目 ---
# 存在しないフォルダパスを指定しても自動で作られます
SOURCE_FOLDER = "F:\SEM\EBSD" # 元の場所
DESTINATION_FOLDER = "./new_folder/backup" # 新しい移動先（無くてもOK）
SEARCH_KEYWORD = "特定"                 # ファイル名に含まれる文字

keywords = ['0.6C', '0.8C', '1.0C']
CR_rates = ['25CR', '50CR', '75CR', '90CR', '93CR', '95CR', '0CR']

if __name__ == "__main__":
    
    for SEARCH_KEYWORD in keywords:
        out_path = Path(fr'{SOURCE_FOLDER}//{SEARCH_KEYWORD}')
        move_files_auto_create_dir(SOURCE_FOLDER, out_path, SEARCH_KEYWORD)
        
        for CR in CR_rates:
            in_path = Path(fr'{SOURCE_FOLDER}//{SEARCH_KEYWORD}')
            out_path = Path(fr'{SOURCE_FOLDER}//{SEARCH_KEYWORD}//{CR}')
            move_files_auto_create_dir(in_path, out_path, CR)
        
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    