from PIL import Image
import os

images = ["C:\\Users\\micae\\sisgen_2\\static\\img\\brasao.png", "C:\\Users\\micae\\sisgen_2\\static\\img\\brasaoappcel.png"]

for img_path in images:
    if os.path.exists(img_path):
        try:
            with Image.open(img_path) as img:
                # Salvar otimizado sem reduzir as dimensões
                img.save(img_path, format="PNG", optimize=True)
            print(f"Otimizado: {img_path}")
        except Exception as e:
            print(f"Erro ao otimizar {img_path}: {e}")
