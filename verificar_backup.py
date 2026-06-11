import zipfile
import os
import glob

# Pasta onde estão os backups
BACKUP_DIR = os.path.join(os.getcwd(), "backups_sistema_full")

def verificar_conteudo():
    print("="*60)
    print("🕵️  AUDITORIA DE INTEGRIDADE DO BACKUP")
    print("="*60)

    # 1. Encontrar o último zip gerado
    arquivos = glob.glob(os.path.join(BACKUP_DIR, '*.zip'))
    if not arquivos:
        print("❌ ERRO: Nenhum arquivo .zip encontrado na pasta de backups.")
        return

    # Pega o mais recente pela data de modificação
    ultimo_backup = max(arquivos, key=os.path.getmtime)
    nome_arq = os.path.basename(ultimo_backup)
    tamanho_mb = os.path.getsize(ultimo_backup) / (1024*1024)

    print(f"📦 Arquivo Analisado: {nome_arq}")
    print(f"⚖️  Tamanho Total:   {tamanho_mb:.2f} MB")
    print("-" * 60)

    try:
        with zipfile.ZipFile(ultimo_backup, 'r') as zf:
            conteudo = zf.namelist()
            
            # 2. Verificar o Banco de Dados (O mais importante)
            if "banco_dados.sql" in conteudo:
                info = zf.getinfo("banco_dados.sql")
                tamanho_sql = info.file_size / (1024*1024)
                print(f"✅ BANCO DE DADOS ENCONTRADO!")
                print(f"   📄 Arquivo: banco_dados.sql")
                print(f"   💾 Tamanho: {tamanho_sql:.2f} MB")
                
                if tamanho_sql < 0.05: # Menos de 50KB é suspeito
                    print("   ⚠️  ALERTA: O banco de dados parece muito pequeno/vazio.")
                else:
                    print("   👍 O tamanho do banco parece saudável.")
            else:
                print("❌ ERRO CRÍTICO: O arquivo 'banco_dados.sql' NÃO está no zip.")

            # 3. Verificar Pastas do Sistema
            print("\n🔍 Verificação de Código e Arquivos:")
            pastas_esperadas = ['backend/', 'templates/', 'static/']
            for pasta in pastas_esperadas:
                # Verifica se existe algum arquivo que comece com o nome da pasta
                tem_pasta = any(f.startswith(pasta) for f in conteudo)
                status = "✅ OK" if tem_pasta else "❌ AUSENTE"
                print(f"   - {pasta:<15} : {status}")

    except zipfile.BadZipFile:
        print("❌ ERRO GRAVE: O arquivo ZIP está corrompido e não pode ser aberto.")

    print("="*60)

if __name__ == "__main__":
    verificar_conteudo()