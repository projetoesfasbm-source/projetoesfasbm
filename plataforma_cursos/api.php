<?php
session_start();
header('Content-Type: application/json');

$data_file = 'cursos_data.json';

// Estrutura de dados inicial (Padrão)
$default_data = [
    'videos' => [
        [
            'id' => 'v1',
            'name' => 'Manual de Sobrevivência do Aluno - Primeiros Passos',
            'category' => 'Alunos',
            'url' => 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
            'thumbnail' => 'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=500&auto=format&fit=crop'
        ],
        [
            'id' => 'v2',
            'name' => 'Guia de Acesso e Direitos de Trânsito Interno',
            'category' => 'Alunos',
            'url' => 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
            'thumbnail' => 'https://images.unsplash.com/photo-1506784983877-45594efa4cbe?w=500&auto=format&fit=crop'
        ],
        [
            'id' => 'v3',
            'name' => 'Diretrizes Acadêmicas e Metodologia de Instrução',
            'category' => 'Instrutores',
            'url' => 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4',
            'thumbnail' => 'https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=500&auto=format&fit=crop'
        ],
        [
            'id' => 'v4',
            'name' => 'Tutorial: Lançamento de Diários de Classe e Presenças',
            'category' => 'Instrutores',
            'url' => 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4',
            'thumbnail' => 'https://images.unsplash.com/photo-1434030216411-0b793f4b4173?w=500&auto=format&fit=crop'
        ],
        [
            'id' => 'v5',
            'name' => 'Painel Administrativo: Auditoria de Logs do Sistema',
            'category' => 'Adm',
            'url' => 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4',
            'thumbnail' => 'https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=500&auto=format&fit=crop'
        ],
        [
            'id' => 'v6',
            'name' => 'Procedimento Operacional: Backup e Migração de Dados',
            'category' => 'Adm',
            'url' => 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutback.mp4',
            'thumbnail' => 'https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=500&auto=format&fit=crop'
        ]
    ],
    'logo' => [
        'type' => 'text',
        'text' => 'SisG<span>En</span> CURSOS',
        'imageUrl' => '',
        'bannerBgType' => 'url',
        'bannerBgUrl' => ''
    ],
    'intro' => [
        'logoText' => 'SisG<span>En</span>',
        'subtext' => 'PLATAFORMA DE CURSOS',
        'duration' => 3
    ]
];

if (!file_exists($data_file)) {
    file_put_contents($data_file, json_encode($default_data, JSON_PRETTY_PRINT));
}

$current_data = json_decode(file_get_contents($data_file), true);

// Retorna os dados globais para todos
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    echo json_encode($current_data);
    exit;
}

// Salva dados (Exige autenticação)
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!isset($_SESSION['cursos_authenticated']) || $_SESSION['cursos_authenticated'] !== true) {
        http_response_code(403);
        echo json_encode(['error' => 'Não autenticado no painel de cursos.']);
        exit;
    }

    $input_data = json_decode(file_get_contents('php://input'), true);

    if ($input_data === null) {
        http_response_code(400);
        echo json_encode(['error' => 'JSON Inválido']);
        exit;
    }

    if (isset($input_data['action'])) {
        if ($input_data['action'] === 'save_videos') {
            $current_data['videos'] = $input_data['videos'];
        } elseif ($input_data['action'] === 'save_logo') {
            $current_data['logo'] = $input_data['logo'];
        } elseif ($input_data['action'] === 'save_intro') {
            $current_data['intro'] = $input_data['intro'];
        } elseif ($input_data['action'] === 'restore_defaults') {
            $current_data = $default_data;
        }
        
        file_put_contents($data_file, json_encode($current_data, JSON_PRETTY_PRINT));
        echo json_encode(['success' => true]);
        exit;
    }

    http_response_code(400);
    echo json_encode(['error' => 'Nenhuma ação válida especificada.']);
    exit;
}
