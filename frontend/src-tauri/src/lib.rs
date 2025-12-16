// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/

/// 앱 버전 정보 반환
#[tauri::command]
fn get_app_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

/// 앱 이름 반환
#[tauri::command]
fn get_app_name() -> String {
    "TriFlow AI".to_string()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_http::init())
        .invoke_handler(tauri::generate_handler![get_app_version, get_app_name])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
