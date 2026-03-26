import os
from pathlib import Path

class TAppHelper:
    """
    Proje dosyaları üzerinde toplu işlemler yapmayı sağlayan yardımcı sınıf.
    """

    @staticmethod
    def add_path_comment():
        """
        Belirtilen kök dizinde ve alt dizinlerinde tüm .py dosyalarına
        dosya yolunu yorum satırı olarak en tepeye ekler. 
        Eğer yol zaten ekliyse tekrar eklemez.
        """
        root_dir = Path.cwd()
        print(f"--- İşlem Başlatıldı ---")
        print(f"Dizin: {root_dir}\n")

        processed_count = 0
        skipped_count = 0

        # Tüm .py dosyalarını bul (rekürsif)
        for py_file in root_dir.rglob("*.py"):
            # Kendi dosyasını (tapphelper.py) değiştirmesini istemeyebilirsin
            if py_file.name == "tapphelper.py" or not py_file.is_file():
                continue
            
            try:
                # Proje köküne göre bağıl yol
                relative_path = py_file.relative_to(root_dir)
                comment_line = f"# {relative_path}\n"
                
                # Dosya içeriğini oku
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.readlines()

                # Kontrol: Yol zaten dosyanın en başında var mı?
                if content and content[0] == comment_line:
                    print(f"Zaten mevcut: {relative_path}")
                    skipped_count += 1
                    continue

                # Yeni içeriği oluştur (Yorum satırı + eski içerik)
                new_content = [comment_line] + content

                # Dosyayı güncelle
                with open(py_file, "w", encoding="utf-8") as f:
                    f.writelines(new_content)
                
                print(f"Eklendi: {relative_path}")
                processed_count += 1

            except (UnicodeDecodeError, PermissionError) as e:
                print(f"Hata! Atlanıyor: {py_file.name} ({e})")
                continue
            except Exception as e:
                print(f"Beklenmedik hata ({py_file.name}): {e}")
                continue

        print(f"\n--- İşlem Tamamlandı ---")
        print(f"Güncellenen: {processed_count} | Atlanan: {skipped_count}") 
    @staticmethod
    def export_folder_tree():
            startpath = Path.cwd()
            output_filename = "folder_structure.txt"

            # Yoksayılacaklar
            IGNORE_DIRS = {'.git', '.vscode', '__pycache__', 'venv', '.idea', 'node_modules'}
            IGNORE_EXTENSIONS = {'.pyc', '.pyo', '.ds_store', '.gitignore'}

            def generate_tree(directory, prefix=""):
                """
                Recursive (Özyinelemeli) olarak klasör yapısını string listesi olarak döndürür.
                Bu yöntem görsel olarak daha sağlamdır.
                """
                tree_lines = []
                
                try:
                    # Klasör içeriğini al ve sırala (Önce klasörler, sonra dosyalar)
                    contents = list(directory.iterdir())
                    contents.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
                except PermissionError:
                    return []

                # Filtreleme işlemi
                items = []
                for item in contents:
                    if item.is_dir():
                        if item.name not in IGNORE_DIRS:
                            items.append(item)
                    else:
                        if item.suffix not in IGNORE_EXTENSIONS and item.name != output_filename:
                            items.append(item)

                # Eleman sayısını al
                count = len(items)
                
                for index, item in enumerate(items):
                    is_last = (index == count - 1)
                    connector = "└── " if is_last else "├── "
                    
                    # Listeye ekle
                    tree_lines.append(f"{prefix}{connector}{item.name}")
                    
                    if item.is_dir():
                        # Bir alt klasöre girerken prefix'i güncelle
                        # Eğer son klasörse boşluk, değilse dikey çizgi (|) ekle
                        extension = "    " if is_last else "│   "
                        tree_lines.extend(generate_tree(item, prefix=prefix + extension))
                
                return tree_lines

            try:
                # Ağacı oluştur
                tree_output = [f"{startpath.name}/"] + generate_tree(startpath)
                
                # Dosyaya yaz (newline karakterini açıkça belirterek)
                with open(output_filename, 'w', encoding='utf-8', newline='\n') as f:
                    f.write("\n".join(tree_output))

                print(f"✅ Klasör yapısı '{output_filename}' dosyasına yazıldı.")

            except Exception as e:
                print(f"❌ Hata: {e}")
            
    @staticmethod
    def fix_path_comments():
        """
        Dosya başındaki yolu kontrol eder:
        - Yanlışsa siler ve doğrusunu ekler.
        - Yoksa ekler.
        - Doğruysa dokunmaz.
        """
        root_dir = Path.cwd()
        print(f"--- Güncelleme İşlemi Başlatıldı ---")

        updated_count = 0
        correct_count = 0

        for py_file in root_dir.rglob("*.py"):
            if py_file.name == "tapphelper.py" or not py_file.is_file():
                continue
            
            try:
                relative_path = py_file.relative_to(root_dir)
                correct_comment = f"# {relative_path}\n"
                
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.readlines()

                needs_update = False
                
                if content and content[0].startswith("# "):
                    if content[0] == correct_comment:
                        # Zaten doğru yol ekli
                        correct_count += 1
                        continue
                    else:
                        # Başında yorum var ama YANLIŞ yol. 
                        # İlk satırı atıp yenisini ekleyeceğiz.
                        content = content[1:]
                        needs_update = True
                else:
                    # Başında hiç yorum satırı yok
                    needs_update = True

                if needs_update:
                    new_content = [correct_comment] + content
                    with open(py_file, "w", encoding="utf-8") as f:
                        f.writelines(new_content)
                    
                    print(f"Güncellendi: {relative_path}")
                    updated_count += 1

            except Exception as e:
                print(f"Hata ({py_file.name}): {e}")

        print(f"\n--- İşlem Tamamlandı ---")
        print(f"Güncellenen/Eklenen: {updated_count} | Zaten Doğru: {correct_count}")