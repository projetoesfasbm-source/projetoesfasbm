// -------------------------------------------------------------
// Plataforma de Cursos SISgem - Lógica e Banco de Dados Local
// -------------------------------------------------------------

// 1. DADOS PADRÃO (Populado se o localStorage estiver vazio)
const defaultVideos = [
    {
        id: "v1",
        name: "Manual de Sobrevivência do Aluno - Primeiros Passos",
        category: "Alunos",
        url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
        thumbnail: "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=500&auto=format&fit=crop"
    },
    {
        id: "v2",
        name: "Guia de Acesso e Direitos de Trânsito Interno",
        category: "Alunos",
        url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        thumbnail: "https://images.unsplash.com/photo-1506784983877-45594efa4cbe?w=500&auto=format&fit=crop"
    },
    {
        id: "v3",
        name: "Diretrizes Acadêmicas e Metodologia de Instrução",
        category: "Instrutores",
        url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4",
        thumbnail: "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=500&auto=format&fit=crop"
    },
    {
        id: "v4",
        name: "Tutorial: Lançamento de Diários de Classe e Presenças",
        category: "Instrutores",
        url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4",
        thumbnail: "https://images.unsplash.com/photo-1434030216411-0b793f4b4173?w=500&auto=format&fit=crop"
    },
    {
        id: "v5",
        name: "Painel Administrativo: Auditoria de Logs do Sistema",
        category: "Adm",
        url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4",
        thumbnail: "https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=500&auto=format&fit=crop"
    },
    {
        id: "v6",
        name: "Procedimento Operacional: Backup e Migração de Dados",
        category: "Adm",
        url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutback.mp4",
        thumbnail: "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=500&auto=format&fit=crop"
    }
];

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

// 2. INICIALIZAÇÃO E CARREGAMENTO
document.addEventListener("DOMContentLoaded", () => {
    // Inicializa o banco de dados no localStorage caso não exista
    if (!localStorage.getItem("sisgem_videos")) {
        localStorage.setItem("sisgem_videos", JSON.stringify(defaultVideos));
    }
    if (!localStorage.getItem("sisgem_watched")) {
        localStorage.setItem("sisgem_watched", JSON.stringify([]));
    }
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

function showMainContent() {
    const introScreen = document.getElementById("intro-screen");
    const mainContent = document.getElementById("main-content");
    
    introScreen.classList.add("hidden");
    mainContent.classList.remove("hidden");
    
    // Evento de clique para o primeiro vídeo em destaque
    const videos = JSON.parse(localStorage.getItem("sisgem_videos")) || [];
    const heroBtn = document.getElementById("hero-play-btn");
    const heroTitle = document.getElementById("hero-title");
    
    if (videos.length > 0) {
        // Encontra o último vídeo adicionado ou o primeiro
        const featuredVideo = videos[0];
        heroTitle.textContent = featuredVideo.name;
        heroBtn.onclick = () => playVideo(featuredVideo.id);
    } else {
        heroBtn.onclick = () => showToast("Nenhum vídeo cadastrado no momento!");
    }
}

// 4. RENDERS DE CONTEÚDO (index.html)
function renderAllShelves() {
    const videos = JSON.parse(localStorage.getItem("sisgem_videos")) || [];
    const watchedList = JSON.parse(localStorage.getItem("sisgem_watched")) || [];

    const rowAlunos = document.getElementById("row-alunos");
    const rowInstrutores = document.getElementById("row-instrutores");
    const rowAdm = document.getElementById("row-adm");

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
        const isWatched = watchedList.includes(video.id);
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
function playVideo(videoId) {
    const videos = JSON.parse(localStorage.getItem("sisgem_videos")) || [];
    const video = videos.find(v => v.id === videoId);
    
    if (!video) return;

    // Atualiza status de visualização para visto (watched)
    markAsWatched(videoId);

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
        // Direct MP4
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
        // Link encurtado do OneDrive Personal
        // Substitui /v/ ou /u/ ou /w/ por /embed/ para obter a visualização incorporável do player
        let embedUrl = url.replace(/\/v\//g, '/embed/').replace(/\/u\//g, '/embed/').replace(/\/w\//g, '/embed/');
        return { type: "iframe", url: embedUrl };
    } else if (url.includes('onedrive.live.com')) {
        // Link longo do OneDrive Personal
        let embedUrl = url;
        if (url.includes('redir?')) {
            embedUrl = url.replace('redir?', 'embed?');
        } else if (!url.includes('embed?')) {
            embedUrl = url + (url.includes('?') ? '&' : '?') + 'action=embedview';
        }
        return { type: "iframe", url: embedUrl };
    } else if (url.includes('sharepoint.com')) {
        // OneDrive for Business ou SharePoint
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

    // Logo settings elements
    document.getElementById("logo-type").value = logoSettings.type;
    document.getElementById("logo-text-input").value = logoSettings.text;
    
    const preview = document.getElementById("logo-preview");
    if (logoSettings.imageUrl) {
        preview.src = logoSettings.imageUrl;
        preview.classList.remove("hidden");
    }

    // Banner background settings elements
    document.getElementById("bg-type").value = logoSettings.bannerBgType || "url";
    document.getElementById("bg-url-input").value = logoSettings.bannerBgUrl || "";
    
    const bgPreview = document.getElementById("bg-preview");
    if (logoSettings.bannerBgType === "upload" && logoSettings.bannerBgUrl) {
        bgPreview.src = logoSettings.bannerBgUrl;
        bgPreview.classList.remove("hidden");
    }

    // Intro settings elements
    document.getElementById("intro-logo-text").value = introSettings.logoText;
    document.getElementById("intro-subtext-input").value = introSettings.subtext;
    document.getElementById("intro-duration").value = introSettings.duration;
}

function toggleLogoInputs() {
    const type = document.getElementById("logo-type").value;
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
    const type = document.getElementById("bg-type").value;
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

// Tabela do Admin
function loadVideosTable() {
    const videos = JSON.parse(localStorage.getItem("sisgem_videos")) || [];
    const tbody = document.getElementById("admin-video-list");
    
    tbody.innerHTML = "";

    if (videos.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">Nenhum vídeo cadastrado.</td></tr>`;
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

function handleAddVideo(event) {
    event.preventDefault();
    
    const name = document.getElementById("video-name").value;
    const category = document.getElementById("video-category").value;
    const url = document.getElementById("video-url").value;
    const thumbnail = document.getElementById("video-thumbnail").value;

    const newVideo = {
        id: "v_" + Date.now(),
        name: name,
        category: category,
        url: url,
        thumbnail: thumbnail || null
    };

    let videos = JSON.parse(localStorage.getItem("sisgem_videos")) || [];
    videos.push(newVideo);
    localStorage.setItem("sisgem_videos", JSON.stringify(videos));

    // Reseta form
    document.getElementById("add-video-form").reset();
    
    loadVideosTable();
    showToast("Vídeo adicionado com sucesso!");
}

function deleteVideo(videoId) {
    if (confirm("Tem certeza que deseja excluir esta vídeo aula?")) {
        let videos = JSON.parse(localStorage.getItem("sisgem_videos")) || [];
        videos = videos.filter(v => v.id !== videoId);
        localStorage.setItem("sisgem_videos", JSON.stringify(videos));

        // Também remove da lista de visualizados se estiver lá
        let watched = JSON.parse(localStorage.getItem("sisgem_watched")) || [];
        watched = watched.filter(id => id !== videoId);
        localStorage.setItem("sisgem_watched", JSON.stringify(watched));

        loadVideosTable();
        showToast("Vídeo removido.");
    }
}

// Ações rápidas
function resetWatchedStatus() {
    localStorage.setItem("sisgem_watched", JSON.stringify([]));
    showToast("Histórico redefinido! Todos os contornos ficaram vermelhos.");
}

function restoreDefaultVideos() {
    if (confirm("Deseja restaurar a lista inicial de vídeos padrão? Isso limpará seus vídeos adicionados.")) {
        localStorage.setItem("sisgem_videos", JSON.stringify(defaultVideos));
        localStorage.setItem("sisgem_watched", JSON.stringify([]));
        loadVideosTable();
        showToast("Lista padrão restaurada.");
    }
}

// 7. TOAST NOTIFICATIONS
function showToast(message) {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.classList.remove("hidden");
    
    setTimeout(() => {
        toast.classList.add("hidden");
    }, 3000);
}
