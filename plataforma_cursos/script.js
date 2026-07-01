// -------------------------------------------------------------
// Plataforma de Cursos SISgem - Lógica e Banco de Dados (API)
// -------------------------------------------------------------

// 1. DADOS PADRÃO (Para Configurações Locais de Layout)
const defaultLogoSettings = {
    type: "text",
    text: "SISG<span>EM</span> CURSOS",
    imageUrl: "",
    bannerBgType: "url",
    bannerBgUrl: ""
};

const defaultIntroSettings = {
    logoText: "SISG<span>EM</span>",
    subtext: "PLATAFORMA DE CURSOS",
    duration: 3
};

// ==========================================
// FUNÇÕES DE COMUNICAÇÃO COM O SERVIDOR
// ==========================================
async function fetchVideosFromServer() {
    try {
        const response = await fetch('/api/cursos/videos');
        if (!response.ok) throw new Error('Erro ao buscar vídeos');
        const videos = await response.json();
        return videos;
    } catch (error) {
        console.error("Erro na API:", error);
        return []; // Retorna array vazio em caso de erro para não quebrar a tela
    }
}

// 2. INICIALIZAÇÃO E CARREGAMENTO
document.addEventListener("DOMContentLoaded", () => {
    // Histórico de assistidos continua local (para cada aluno ter o seu)
    if (!localStorage.getItem("sisgem_watched")) {
        localStorage.setItem("sisgem_watched", JSON.stringify([]));
    }
    // Configurações visuais continuam locais
    if (!localStorage.getItem("sisgem_logo")) {
        localStorage.setItem("sisgem_logo", JSON.stringify(defaultLogoSettings));
    }
    if (!localStorage.getItem("sisgem_intro")) {
        localStorage.setItem("sisgem_intro", JSON.stringify(defaultIntroSettings));
    }

    // Se estivermos na página principal, roda a intro e renderiza
    if (document.getElementById("intro-screen")) {
        runIntroSequence();
        applyCustomLogo();
        renderAllShelves();
    }
});

// 3. INTRO SEQUENCE (ESTILO NETFLIX)
function runIntroSequence() {
    const introSettings = JSON.parse(localStorage.getItem("sisgem_intro")) || defaultIntroSettings;
    
    // Atualiza elementos da intro baseado nos dados salvos
    const introLogo = document.getElementById("intro-logo");
    const introSub = document.querySelector(".intro-subtext");
    const introScreen = document.getElementById("intro-screen");
    const mainContent = document.getElementById("main-content");
    
    introLogo.innerHTML = introSettings.logoText;
    introSub.textContent = introSettings.subtext;
    
    // Define a duração da animação no CSS através de variável ou timeout
    const durationMs = introSettings.duration * 1000;
    
    // Ajusta animação para a duração customizada
    introLogo.style.animationDuration = `${introSettings.duration + 0.5}s`;
    introScreen.style.animation = `fadeOutIntro 0.5s ease ${introSettings.duration}s forwards`;
    
    // Mostra o conteúdo principal após a intro
    const transitionTimeout = setTimeout(() => {
        showMainContent();
    }, durationMs);

    // Evento de Pular Intro
    document.getElementById("skip-intro").addEventListener("click", () => {
        clearTimeout(transitionTimeout);
        showMainContent();
    });
}

async function showMainContent() {
    const introScreen = document.getElementById("intro-screen");
    const mainContent = document.getElementById("main-content");
    
    introScreen.classList.add("hidden");
    mainContent.classList.remove("hidden");
    
    // Evento de clique para o primeiro vídeo em destaque (Buscando do Servidor)
    const videos = await fetchVideosFromServer();
    const heroBtn = document.getElementById("hero-play-btn");
    const heroTitle = document.getElementById("hero-title");
    
    if (videos.length > 0) {
        // Encontra o vídeo mais recente para o destaque
        const featuredVideo = videos[0];
        heroTitle.textContent = featuredVideo.name;
        heroBtn.onclick = () => playVideo(featuredVideo.id);
    } else {
        heroBtn.onclick = () => showToast("Nenhum vídeo cadastrado no momento!");
    }
}

// 4. RENDERS DE CONTEÚDO (index.html)
async function renderAllShelves() {
    // Busca os vídeos do banco de dados em vez do localStorage
    const videos = await fetchVideosFromServer();
    const watchedList = JSON.parse(localStorage.getItem("sisgem_watched")) || [];

    const rowAlunos = document.getElementById("row-alunos");
    const rowInstrutores = document.getElementById("row-instrutores");
    const rowAdm = document.getElementById("row-adm");

    if (!rowAlunos || !rowInstrutores || !rowAdm) return; // Proteção para não dar erro na página admin

    // Limpa carrosséis
    rowAlunos.innerHTML = "";
    rowInstrutores.innerHTML = "";
    rowAdm.innerHTML = "";

    const categories = {
        "Alunos": { container: rowAlunos, count: 0 },
        "Instrutores": { container: rowInstrutores, count: 0 },
        "Adm": { container: rowAdm, count: 0 }
    };

    videos.forEach(video => {
        const isWatched = watchedList.includes(video.id.toString());
        const cardClass = isWatched ? "watched" : "unwatched";
        const badgeText = isWatched ? "Visto" : "Não Visto";
        
        // Thumbnail logic: fallbacks to categories gradients if url empty
        const bgStyle = video.thumbnail 
            ? `style="background-image: url('${video.thumbnail}')"` 
            : `style="background-image: linear-gradient(135deg, var(--primary-blue) 0%, var(--bg-card) 100%)"`;

        const cardHtml = `
            <div class="video-card ${cardClass}" onclick="playVideo('${video.id}')">
                <div class="card-thumbnail" ${bgStyle}>
                    <div class="play-hover-btn"><i class="fas fa-play"></i></div>
                </div>
                <div class="card-content-overlay">
                    <h3 class="video-card-title">${video.name}</h3>
                    <div class="video-card-meta">
                        <span class="status-badge">${badgeText}</span>
                        <span class="video-duration"><i class="far fa-clock"></i> Aula</span>
                    </div>
                </div>
            </div>
        `;

        if (categories[video.category]) {
            categories[video.category].container.insertAdjacentHTML("beforeend", cardHtml);
            categories[video.category].count++;
        }
    });

    // Adiciona placeholders se a categoria estiver vazia
    Object.keys(categories).forEach(catName => {
        if (categories[catName].count === 0) {
            categories[catName].container.innerHTML = `<div class="empty-row-text">Nenhuma vídeo aula cadastrada para a categoria ${catName}.</div>`;
        }
    });
}

function applyCustomLogo() {
    const logoSettings = JSON.parse(localStorage.getItem("sisgem_logo")) || defaultLogoSettings;
    const navText = document.getElementById("nav-logo-text");
    const navImg = document.getElementById("nav-logo-img");

    if (logoSettings.type === "image" && logoSettings.imageUrl) {
        navText.classList.add("hidden");
        navImg.src = logoSettings.imageUrl;
        navImg.classList.remove("hidden");
    } else {
        navImg.classList.add("hidden");
        navText.innerHTML = logoSettings.text || "SISG<span>EM</span> CURSOS";
        navText.classList.remove("hidden");
    }

    // Aplica a imagem de fundo do banner (destaque)
    const heroBanner = document.getElementById("hero-banner");
    if (heroBanner) {
        const bgUrl = logoSettings.bannerBgUrl || 'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=1600&auto=format&fit=crop';
        heroBanner.style.backgroundImage = `linear-gradient(to right, rgba(9, 12, 16, 0.9) 30%, rgba(9, 12, 16, 0.2) 70%), url('${bgUrl}')`;
    }
}

// 5. PLAYER DE VÍDEO (Netflix Modal Style)
async function playVideo(videoId) {
    const videos = await fetchVideosFromServer();
    const video = videos.find(v => v.id.toString() === videoId.toString());
    
    if (!video) return;

    // Atualiza status de visualização para visto (watched)
    markAsWatched(videoId.toString());

    // Seleciona elementos do modal
    const modal = document.getElementById("player-modal");
    const container = document.getElementById("video-container");
    const modalTitle = document.getElementById("modal-video-title");
    const modalCategory = document.getElementById("modal-video-category");
    
    modalTitle.textContent = video.name;
    modalCategory.textContent = video.category;

    // Define player HTML (suporta MP4 direto, YouTube Link ou OneDrive/SharePoint Embed)
    let playerHtml = "";
    const parsedUrl = parseVideoUrl(video.url);

    if (parsedUrl.type === "youtube" || parsedUrl.type === "iframe") {
        playerHtml = `<iframe src="${parsedUrl.url}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>`;
    } else {
        // Direct MP4 - Modificado para tocar com as tags solicitadas
        playerHtml = `
            <video src="${video.url}" controls autoplay playsinline preload="auto">
                Seu navegador não suporta a tag de vídeo.
            </video>
        `;
    }

    container.innerHTML = playerHtml;
    modal.classList.remove("hidden");
    document.body.style.overflow = "hidden"; // Desabilita scroll do body
}

function closePlayer() {
    const modal = document.getElementById("player-modal");
    const container = document.getElementById("video-container");
    
    container.innerHTML = ""; // Para a reprodução do vídeo
    modal.classList.add("hidden");
    document.body.style.overflow = ""; // Reabilita scroll do body
    
    // Atualiza a interface
    renderAllShelves();
}

function parseVideoUrl(url) {
    if (url.includes('youtube.com/watch?v=')) {
        let videoId = url.split('v=')[1].split('&')[0];
        return { type: "youtube", url: `https://www.youtube.com/embed/${videoId}?autoplay=1&rel=0` };
    } else if (url.includes('youtu.be/')) {
        let videoId = url.split('youtu.be/')[1].split('?')[0];
        return { type: "youtube", url: `https://www.youtube.com/embed/${videoId}?autoplay=1&rel=0` };
    } else if (url.includes('youtube.com/embed/')) {
        return { type: "youtube", url: url };
    } else if (url.includes('1drv.ms')) {
        let embedUrl = url.replace(/\/v\//g, '/embed/').replace(/\/u\//g, '/embed/').replace(/\/w\//g, '/embed/');
        return { type: "iframe", url: embedUrl };
    } else if (url.includes('onedrive.live.com')) {
        let embedUrl = url;
        if (url.includes('redir?')) {
            embedUrl = url.replace('redir?', 'embed?');
        } else if (!url.includes('embed?')) {
            embedUrl = url + (url.includes('?') ? '&' : '?') + 'action=embedview';
        }
        return { type: "iframe", url: embedUrl };
    } else if (url.includes('sharepoint.com')) {
        let embedUrl = url;
        if (!url.includes('action=embedview')) {
            embedUrl = url + (url.includes('?') ? '&' : '?') + 'action=embedview';
        }
        return { type: "iframe", url: embedUrl };
    }
    return { type: "direct", url: url };
}

function markAsWatched(videoId) {
    let watchedList = JSON.parse(localStorage.getItem("sisgem_watched")) || [];
    if (!watchedList.includes(videoId)) {
        watchedList.push(videoId);
        localStorage.setItem("sisgem_watched", JSON.stringify(watchedList));
    }
}

// Lógica de Scroll Horizontal dos Carrosséis
function scrollRow(btn, direction) {
    const outerWrapper = btn.closest(".row-outer-wrapper");
    const carousel = outerWrapper.querySelector(".row-inner-carousel");
    const scrollAmount = 400;
    carousel.scrollBy({ left: scrollAmount * direction, behavior: "smooth" });
}

// 6. ADMIN PAGE LOGIC (admin.html)
function initAdminPage() {
    loadBrandingData();
    loadVideosTable();
    toggleLogoInputs();
    toggleBgInputs();
}

function loadBrandingData() {
    const logoSettings = JSON.parse(localStorage.getItem("sisgem_logo")) || defaultLogoSettings;
    const introSettings = JSON.parse(localStorage.getItem("sisgem_intro")) || defaultIntroSettings;

    const typeInput = document.getElementById("logo-type");
    if(typeInput) typeInput.value = logoSettings.type;
    
    const textInput = document.getElementById("logo-text-input");
    if(textInput) textInput.value = logoSettings.text;
    
    const preview = document.getElementById("logo-preview");
    if (preview && logoSettings.imageUrl) {
        preview.src = logoSettings.imageUrl;
        preview.classList.remove("hidden");
    }

    const bgType = document.getElementById("bg-type");
    if(bgType) bgType.value = logoSettings.bannerBgType || "url";
    
    const bgUrlInput = document.getElementById("bg-url-input");
    if(bgUrlInput) bgUrlInput.value = logoSettings.bannerBgUrl || "";
    
    const bgPreview = document.getElementById("bg-preview");
    if (bgPreview && logoSettings.bannerBgType === "upload" && logoSettings.bannerBgUrl) {
        bgPreview.src = logoSettings.bannerBgUrl;
        bgPreview.classList.remove("hidden");
    }

    const introLogoText = document.getElementById("intro-logo-text");
    if(introLogoText) introLogoText.value = introSettings.logoText;
    
    const introSub = document.getElementById("intro-subtext-input");
    if(introSub) introSub.value = introSettings.subtext;
    
    const introDur = document.getElementById("intro-duration");
    if(introDur) introDur.value = introSettings.duration;
}

function toggleLogoInputs() {
    const typeElement = document.getElementById("logo-type");
    if(!typeElement) return;
    
    const type = typeElement.value;
    const textGroup = document.getElementById("logo-text-group");
    const imgGroup = document.getElementById("logo-image-group");

    if (type === "image") {
        textGroup.classList.add("hidden");
        imgGroup.classList.remove("hidden");
    } else {
        imgGroup.classList.add("hidden");
        textGroup.classList.remove("hidden");
    }
}

let uploadedLogoBase64 = "";

function handleLogoUpload(input) {
    const file = input.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        uploadedLogoBase64 = e.target.result;
        const preview = document.getElementById("logo-preview");
        preview.src = uploadedLogoBase64;
        preview.classList.remove("hidden");
    };
    reader.readAsDataURL(file);
}

function toggleBgInputs() {
    const typeElement = document.getElementById("bg-type");
    if(!typeElement) return;
    
    const type = typeElement.value;
    const urlGroup = document.getElementById("bg-url-group");
    const uploadGroup = document.getElementById("bg-upload-group");

    if (type === "upload") {
        urlGroup.classList.add("hidden");
        uploadGroup.classList.remove("hidden");
    } else {
        uploadGroup.classList.add("hidden");
        urlGroup.classList.remove("hidden");
    }
}

let uploadedBgBase64 = "";

function handleBgUpload(input) {
    const file = input.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        uploadedBgBase64 = e.target.result;
        const preview = document.getElementById("bg-preview");
        preview.src = uploadedBgBase64;
        preview.classList.remove("hidden");
    };
    reader.readAsDataURL(file);
}

function saveLogoSettings() {
    const type = document.getElementById("logo-type").value;
    const textVal = document.getElementById("logo-text-input").value;
    const bgType = document.getElementById("bg-type").value;
    const bgUrlVal = document.getElementById("bg-url-input").value;
    
    let logoSettings = JSON.parse(localStorage.getItem("sisgem_logo")) || defaultLogoSettings;
    logoSettings.type = type;
    logoSettings.text = textVal;
    logoSettings.bannerBgType = bgType;

    if (type === "image" && uploadedLogoBase64) {
        logoSettings.imageUrl = uploadedLogoBase64;
    }

    if (bgType === "upload" && uploadedBgBase64) {
        logoSettings.bannerBgUrl = uploadedBgBase64;
    } else if (bgType === "url") {
        logoSettings.bannerBgUrl = bgUrlVal;
    }

    localStorage.setItem("sisgem_logo", JSON.stringify(logoSettings));
    showToast("Identidade Visual salva com sucesso!");
}

function saveIntroSettings() {
    const introLogo = document.getElementById("intro-logo-text").value;
    const introSub = document.getElementById("intro-subtext-input").value;
    const introDur = parseFloat(document.getElementById("intro-duration").value) || 3;

    const introSettings = {
        logoText: introLogo,
        subtext: introSub,
        duration: introDur
    };

    localStorage.setItem("sisgem_intro", JSON.stringify(introSettings));
    showToast("Configurações da intro salvas!");
}

// Tabela do Admin - AGORA BUSCANDO DO SERVIDOR
async function loadVideosTable() {
    const videos = await fetchVideosFromServer();
    const tbody = document.getElementById("admin-video-list");
    
    if(!tbody) return;

    tbody.innerHTML = "";

    if (videos.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">Nenhum vídeo cadastrado no servidor.</td></tr>`;
        return;
    }

    videos.forEach(video => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>${video.name}</strong></td>
            <td><span class="category-tag">${video.category}</span></td>
            <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                <a href="${video.url}" target="_blank" style="color: var(--primary-light);">${video.url}</a>
            </td>
            <td>
                <button onclick="deleteVideo('${video.id}')" class="btn-delete" title="Deletar Vídeo">
                    <i class="fas fa-trash-can"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// Adicionar Vídeo - AGORA SALVANDO NO SERVIDOR
async function handleAddVideo(event) {
    event.preventDefault();
    
    const submitBtn = document.querySelector("#add-video-form button[type='submit']");
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Salvando...';
    submitBtn.disabled = true;
    
    const name = document.getElementById("video-name").value;
    const category = document.getElementById("video-category").value;
    const url = document.getElementById("video-url").value;
    const thumbnail = document.getElementById("video-thumbnail").value;

    const newVideo = {
        name: name,
        category: category,
        url: url,
        thumbnail: thumbnail || null
    };

    try {
        const response = await fetch('/api/cursos/videos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newVideo)
        });

        if (response.ok) {
            document.getElementById("add-video-form").reset();
            loadVideosTable();
            showToast("Vídeo adicionado com sucesso ao servidor!");
        } else {
            showToast("Erro ao salvar vídeo no servidor.");
        }
    } catch (error) {
        console.error(error);
        showToast("Erro de conexão com o servidor.");
    } finally {
        submitBtn.innerHTML = '<i class="fas fa-plus"></i> Adicionar Vídeo';
        submitBtn.disabled = false;
    }
}

// Deletar Vídeo - AGORA EXCLUINDO DO SERVIDOR
async function deleteVideo(videoId) {
    if (confirm("Tem certeza que deseja excluir esta vídeo aula do servidor?")) {
        try {
            const response = await fetch(`/api/cursos/videos/${videoId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                // Também remove da lista local de visualizados
                let watched = JSON.parse(localStorage.getItem("sisgem_watched")) || [];
                watched = watched.filter(id => id !== videoId.toString());
                localStorage.setItem("sisgem_watched", JSON.stringify(watched));

                loadVideosTable();
                showToast("Vídeo removido com sucesso!");
            } else {
                showToast("Erro ao tentar remover o vídeo.");
            }
        } catch (error) {
            console.error(error);
            showToast("Erro de conexão com o servidor.");
        }
    }
}

// Ações rápidas
function resetWatchedStatus() {
    localStorage.setItem("sisgem_watched", JSON.stringify([]));
    showToast("Histórico redefinido! Todos os contornos ficaram vermelhos.");
    renderAllShelves(); // Atualiza a interface instantaneamente
}

function restoreDefaultVideos() {
    showToast("Os vídeos agora são gerenciados pelo servidor. Para adicionar novos, preencha o formulário acima.");
}

// 7. TOAST NOTIFICATIONS
function showToast(message) {
    const toast = document.getElementById("toast");
    if(!toast) return;

    toast.textContent = message;
    toast.classList.remove("hidden");
    
    setTimeout(() => {
        toast.classList.add("hidden");
    }, 3000);
}
