<?php
session_start();

$config_password = 'Sisgen@2026';
$error = '';

if (isset($_GET['logout'])) {
    session_destroy();
    header('Location: admin_painel.php');
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action']) && $_POST['action'] === 'login') {
    if (isset($_POST['password']) && $_POST['password'] === $config_password) {
        $_SESSION['cursos_authenticated'] = true;
        header('Location: admin_painel.php');
        exit;
    } else {
        $error = 'Senha incorreta!';
    }
}

$authenticated = $_SESSION['cursos_authenticated'] ?? false;
?>
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Painel de Controle - SisGEn Cursos</title>
    <!-- Google Fonts (Inter) -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <!-- FontAwesome for Icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <!-- Custom CSS -->
    <link rel="stylesheet" href="style.css">
</head>
<body class="admin-body">

    <?php if (!$authenticated): ?>
        <div class="admin-container" style="display: flex; justify-content: center; align-items: center; min-height: 80vh;">
            <div class="admin-card" style="width: 100%; max-width: 400px; padding: 2rem; text-align: center;">
                <h2 style="margin-bottom: 1.5rem;">Login Painel de Cursos</h2>
                <?php if ($error): ?>
                    <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); color: #f87171; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;"><?= htmlspecialchars($error) ?></div>
                <?php endif; ?>
                <form method="POST">
                    <input type="hidden" name="action" value="login">
                    <div class="form-group" style="text-align: left;">
                        <label for="password">Senha de Acesso</label>
                        <input type="password" id="password" name="password" class="form-control" placeholder="Senha" required>
                    </div>
                    <button type="submit" class="btn btn-save" style="width: 100%;">Entrar</button>
                </form>
            </div>
        </div>
    <?php else: ?>

    <div class="admin-container">
        
        <!-- Sidebar/Header back link -->
        <header class="admin-header">
            <div class="admin-title-area">
                <a href="index.html" class="back-btn"><i class="fas fa-chevron-left"></i> Voltar &agrave; Plataforma</a>
                <a href="?logout=1" class="btn-delete" style="float: right; padding: 0.5rem 1rem; border-radius: 6px; text-decoration: none; display: inline-flex; align-items: center; gap: 0.5rem; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); color: #fca5a5;"><i class="fas fa-sign-out-alt"></i> Sair</a>
                <h1>Painel de Controle do Conte&uacute;do</h1>
                <p>Gerencie as configura&ccedil;&otilde;es da plataforma de cursos local</p>
            </div>
        </header>

        <div class="admin-grid">
            
            <!-- Column 1: Configuration Forms -->
            <div class="admin-col">
                
                <!-- Card 1: Logo & General Branding -->
                <div class="admin-card">
                    <div class="admin-card-header">
                        <h2><i class="fas fa-image"></i> Identidade Visual &amp; Logo</h2>
                    </div>
                    <div class="admin-card-body">
                        <div class="form-group">
                            <label for="logo-type">Tipo de Logo</label>
                            <select id="logo-type" class="form-control" onchange="toggleLogoInputs()">
                                <option value="text">Texto Customizado</option>
                                <option value="image">Imagem (Upload ou URL)</option>
                            </select>
                        </div>
                        
                        <div id="logo-text-group" class="form-group">
                            <label for="logo-text-input">Texto do Logo (ex: SisG<span>En</span>)</label>
                            <input type="text" id="logo-text-input" class="form-control" placeholder="SisG<span>En</span>">
                            <small class="form-help">Dica: Use &lt;span&gt; para dar destaque em partes do texto.</small>
                        </div>

                        <div id="logo-image-group" class="form-group hidden">
                            <label for="logo-file-input">Upload de Imagem (Logo)</label>
                            <input type="file" id="logo-file-input" class="form-control" accept="image/*" onchange="handleLogoUpload(this)">
                            <div class="logo-preview-container">
                                <img id="logo-preview" src="" alt="Previsualiza&ccedil;&atilde;o" class="hidden">
                            </div>
                        </div>

                        <!-- Configura&ccedil;&atilde;o do Fundo do Banner -->
                        <div class="form-group" style="margin-top: 1.5rem; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 1.5rem;">
                            <label for="bg-type">Imagem de Fundo do Banner (Destaque)</label>
                            <select id="bg-type" class="form-control" onchange="toggleBgInputs()">
                                <option value="url">Link da Imagem (URL)</option>
                                <option value="upload">Upload de Imagem</option>
                            </select>
                        </div>

                        <div id="bg-url-group" class="form-group">
                            <label for="bg-url-input">URL da Imagem de Fundo</label>
                            <input type="url" id="bg-url-input" class="form-control" placeholder="https://images.unsplash.com/...">
                        </div>

                        <div id="bg-upload-group" class="form-group hidden">
                            <label for="bg-file-input">Upload de Imagem de Fundo</label>
                            <input type="file" id="bg-file-input" class="form-control" accept="image/*" onchange="handleBgUpload(this)">
                            <div class="logo-preview-container">
                                <img id="bg-preview" src="" alt="Previsualiza&ccedil;&atilde;o Fundo" style="max-height: 100px; width: 100%; object-fit: cover;" class="hidden">
                            </div>
                        </div>

                        <button onclick="saveLogoSettings()" class="btn btn-save" style="margin-top: 1rem;"><i class="fas fa-floppy-disk"></i> Salvar Identidade</button>
                    </div>
                </div>

                <!-- Card 2: Intro Animation Configuration -->
                <div class="admin-card">
                    <div class="admin-card-header">
                        <h2><i class="fas fa-clapperboard"></i> Configura&ccedil;&otilde;es da Intro (Estilo Netflix)</h2>
                    </div>
                    <div class="admin-card-body">
                        <div class="form-group">
                            <label for="intro-logo-text">Texto Central da Intro</label>
                            <input type="text" id="intro-logo-text" class="form-control" placeholder="SisG<span>En</span>">
                        </div>
                        <div class="form-group">
                            <label for="intro-subtext-input">Subtexto da Intro</label>
                            <input type="text" id="intro-subtext-input" class="form-control" placeholder="PLATAFORMA DE CURSOS">
                        </div>
                        <div class="form-group">
                            <label for="intro-duration">Dura&ccedil;&atilde;o da Intro (segundos)</label>
                            <input type="number" id="intro-duration" class="form-control" min="1" max="15" value="3">
                        </div>
                        <button onclick="saveIntroSettings()" class="btn btn-save"><i class="fas fa-floppy-disk"></i> Salvar Intro</button>
                    </div>
                </div>

                <!-- Card 3: Add Video Form -->
                <div class="admin-card">
                    <div class="admin-card-header">
                        <h2><i class="fas fa-circle-plus"></i> Adicionar Nova V&iacute;deo Aula</h2>
                    </div>
                    <div class="admin-card-body">
                        <form id="add-video-form" onsubmit="handleAddVideo(event)">
                            <div class="form-group">
                                <label for="video-name">Nome do V&iacute;deo</label>
                                <input type="text" id="video-name" class="form-control" required placeholder="Ex: Aula 01 - Primeiros Passos no SisGEn">
                            </div>
                            <div class="form-group">
                                <label for="video-category">Categoria</label>
                                <select id="video-category" class="form-control" required>
                                    <option value="Alunos">Alunos</option>
                                    <option value="Instrutores">Instrutores</option>
                                    <option value="Adm">Adm</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="video-url">URL do V&iacute;deo (MP4 direto ou Link do YouTube)</label>
                                <input type="url" id="video-url" class="form-control" required placeholder="Ex: https://www.youtube.com/watch?v=dQw4w9WgXcQ">
                                <small class="form-help">Suporta arquivos directos .mp4 e links de reprodu&ccedil;&atilde;o do YouTube.</small>
                            </div>
                            <div class="form-group">
                                <label for="video-thumbnail">URL da Imagem de Capa (Opcional)</label>
                                <input type="url" id="video-thumbnail" class="form-control" placeholder="Ex: https://images.unsplash.com/photo-1516321318423-f06f85e504b3">
                                <small class="form-help">Deixe em branco para usar uma capa padr&atilde;o com base na categoria.</small>
                            </div>
                            <button type="submit" class="btn btn-add"><i class="fas fa-plus"></i> Adicionar V&iacute;deo</button>
                        </form>
                    </div>
                </div>

            </div>

            <!-- Column 2: Video List & Database Stats -->
            <div class="admin-col">
                
                <!-- Card 4: Quick Actions -->
                <div class="admin-card">
                    <div class="admin-card-header">
                        <h2><i class="fas fa-bolt"></i> A&ccedil;&otilde;es R&aacute;pidas</h2>
                    </div>
                    <div class="admin-card-body admin-actions-row">
                        <button onclick="resetWatchedStatus()" class="btn btn-warning"><i class="fas fa-eye-slash"></i> Redefinir todos os V&iacute;deos para N&atilde;o Vistos (Neon Vermelho)</button>
                        <button onclick="restoreDefaultVideos()" class="btn btn-danger"><i class="fas fa-rotate-left"></i> Restaurar V&iacute;deos Padr&atilde;o</button>
                    </div>
                </div>

                <!-- Card 5: Videos Management Table -->
                <div class="admin-card">
                    <div class="admin-card-header">
                        <h2><i class="fas fa-video"></i> Gerenciar V&iacute;deos Cadastrados</h2>
                    </div>
                    <div class="admin-card-body">
                        <div class="table-responsive">
                            <table class="admin-table">
                                <thead>
                                    <tr>
                                        <th>Nome</th>
                                        <th>Categoria</th>
                                        <th>URL</th>
                                        <th>A&ccedil;&otilde;es</th>
                                    </tr>
                                </thead>
                                <tbody id="admin-video-list">
                                    <!-- Injected via JavaScript -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

            </div>

        </div>

    </div>

    <?php endif; ?>

    <!-- Alert toast notification -->
    <div id="toast" class="toast hidden">Mensagem de Sucesso!</div>

    <!-- Script JS -->
    <script src="script.js?v=3"></script>
    <script>
        // Carrega os dados espec&iacute;ficos na p&aacute;gina admin
        document.addEventListener("DOMContentLoaded", () => {
            if (typeof initAdminPage === 'function') {
                initAdminPage();
            }
        });
    </script>
</body>
</html>
