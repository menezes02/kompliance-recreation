(() => {
  const supported = new Set(["en", "pt", "es"]);
  const entries = {
    "Preparing your workspace": ["A preparar o seu espaço de trabalho", "Preparando su espacio de trabajo"],
    "Close navigation": ["Fechar navegação", "Cerrar navegación"], "Open navigation": ["Abrir navegação", "Abrir navegación"],
    "Safety workspace": ["Espaço de segurança", "Espacio de seguridad"], "Production snapshot": ["Cópia de produção", "Copia de producción"],
    "Isolated tenant": ["Empresa isolada", "Empresa aislada"], "Overview": ["Visão geral", "Resumen"], "Workforce": ["Força de trabalho", "Personal"],
    "Workers": ["Trabalhadores", "Trabajadores"], "Shared worker passports": ["Passaportes partilhados", "Pasaportes compartidos"],
    "Workflow & inbox": ["Fluxos e caixa de entrada", "Flujos y bandeja"], "Sites": ["Obras", "Obras"], "Roles": ["Funções", "Funciones"],
    "Subcontractors": ["Subempreiteiros", "Subcontratistas"], "Forms": ["Formulários", "Formularios"], "Form builder": ["Criador de formulários", "Editor de formularios"],
    "Distributions": ["Distribuições", "Distribuciones"], "Inductions": ["Induções", "Inducciones"], "Training": ["Formação", "Formación"],
    "Assets": ["Equipamentos", "Equipos"], "Compliance forms": ["Formulários de conformidade", "Formularios de cumplimiento"],
    "Scaffold Inspections": ["Inspeções de andaimes", "Inspecciones de andamios"], "Handover Certificates": ["Certificados de entrega", "Certificados de entrega"],
    "Risk Assessments": ["Avaliações de risco", "Evaluaciones de riesgos"], "Documents": ["Documentos", "Documentos"],
    "Source archive": ["Arquivo de origem", "Archivo de origen"], "Local workflows": ["Fluxos locais", "Flujos locales"],
    "Expiry centre": ["Centro de validades", "Centro de vencimientos"], "Secure clone": ["Cópia segura", "Copia segura"],
    "Production is read-only": ["A produção é só de leitura", "La producción es de solo lectura"], "Company data is isolated": ["Os dados da empresa estão isolados", "Los datos de la empresa están aislados"],
    "Health & Safety Operations": ["Operações de Saúde e Segurança", "Operaciones de Salud y Seguridad"], "Language": ["Idioma", "Idioma"], "Help": ["Ajuda", "Ayuda"],
    "Company profile": ["Perfil da empresa", "Perfil de la empresa"], "Security settings": ["Definições de segurança", "Configuración de seguridad"],
    "Audit log": ["Registo de auditoria", "Registro de auditoría"], "Access management": ["Gestão de acessos", "Gestión de accesos"],
    "System & privacy": ["Sistema e privacidade", "Sistema y privacidad"], "Contact support": ["Contactar suporte", "Contactar soporte"], "Sign out": ["Terminar sessão", "Cerrar sesión"],
    "Privacy": ["Privacidade", "Privacidad"], "Dashboard": ["Painel", "Panel"], "Search": ["Pesquisar", "Buscar"], "Filter": ["Filtrar", "Filtrar"],
    "Filters": ["Filtros", "Filtros"], "Clear filters": ["Limpar filtros", "Limpiar filtros"], "Apply filters": ["Aplicar filtros", "Aplicar filtros"],
    "All sites": ["Todas as obras", "Todas las obras"], "All workers": ["Todos os trabalhadores", "Todos los trabajadores"], "All statuses": ["Todos os estados", "Todos los estados"],
    "Created date": ["Data de criação", "Fecha de creación"], "Submitted date": ["Data de submissão", "Fecha de envío"], "Newest first": ["Mais recente primeiro", "Más reciente primero"],
    "Oldest first": ["Mais antigo primeiro", "Más antiguo primero"], "Previous": ["Anterior", "Anterior"], "Next": ["Seguinte", "Siguiente"],
    "View": ["Ver", "Ver"], "Download": ["Descarregar", "Descargar"], "Edit": ["Editar", "Editar"], "Delete": ["Eliminar", "Eliminar"],
    "Save": ["Guardar", "Guardar"], "Cancel": ["Cancelar", "Cancelar"], "Close": ["Fechar", "Cerrar"], "Create": ["Criar", "Crear"],
    "Update": ["Atualizar", "Actualizar"], "Add": ["Adicionar", "Añadir"], "Remove": ["Remover", "Quitar"], "Active": ["Ativo", "Activo"], "Inactive": ["Inativo", "Inactivo"],
    "Pending": ["Pendente", "Pendiente"], "Approved": ["Aprovado", "Aprobado"], "Declined": ["Recusado", "Rechazado"], "Completed": ["Concluído", "Completado"],
    "Current": ["Válido", "Vigente"], "Overdue": ["Em atraso", "Vencido"], "Due soon": ["A vencer", "Próximo a vencer"], "Missing date": ["Data em falta", "Fecha faltante"],
    "Name": ["Nome", "Nombre"], "Email": ["Email", "Correo"], "Phone": ["Telefone", "Teléfono"], "Address": ["Morada", "Dirección"], "Status": ["Estado", "Estado"],
    "Actions": ["Ações", "Acciones"], "Created at": ["Criado em", "Creado el"], "Updated at": ["Atualizado em", "Actualizado el"], "Worker name": ["Nome do trabalhador", "Nombre del trabajador"],
    "Site name": ["Nome da obra", "Nombre de la obra"], "Company": ["Empresa", "Empresa"], "Department": ["Departamento", "Departamento"], "Priority": ["Prioridade", "Prioridad"],
    "Subject": ["Assunto", "Asunto"], "Message": ["Mensagem", "Mensaje"], "Due date": ["Data limite", "Fecha límite"], "Type": ["Tipo", "Tipo"],
    "No records found": ["Nenhum registo encontrado", "No se encontraron registros"], "No notifications.": ["Sem notificações.", "Sin notificaciones."],
    "No requests yet.": ["Ainda não existem pedidos.", "Aún no hay solicitudes."], "No induction reviews yet.": ["Ainda não existem revisões de indução.", "Aún no hay revisiones de inducción."],
    "Workflow & inbox": ["Fluxos e caixa de entrada", "Flujos y bandeja"],
    "Route safety requests, review inductions and keep worker conversations in one tenant-scoped workspace": ["Encaminhe pedidos de segurança, reveja induções e mantenha conversas com trabalhadores num único espaço isolado", "Dirija solicitudes de seguridad, revise inducciones y mantenga conversaciones con trabajadores en un espacio aislado"],
    "Active requests": ["Pedidos ativos", "Solicitudes activas"], "Open across all departments": ["Abertos em todos os departamentos", "Abiertas en todos los departamentos"],
    "Pending inductions": ["Induções pendentes", "Inducciones pendientes"], "Awaiting supervisor decision": ["A aguardar decisão do supervisor", "Esperando decisión del supervisor"],
    "Unread": ["Não lidas", "No leídas"], "In-app notifications": ["Notificações na aplicação", "Notificaciones en la aplicación"],
    "Routed work": ["Trabalho encaminhado", "Trabajo dirigido"], "Requests": ["Pedidos", "Solicitudes"],
    "Requests are automatically assigned to the first active contact in the selected department.": ["Os pedidos são atribuídos automaticamente ao primeiro contacto ativo do departamento selecionado.", "Las solicitudes se asignan automáticamente al primer contacto activo del departamento seleccionado."],
    "Worker (optional)": ["Trabalhador (opcional)", "Trabajador (opcional)"], "Internal request": ["Pedido interno", "Solicitud interna"], "Create request": ["Criar pedido", "Crear solicitud"],
    "Approvals": ["Aprovações", "Aprobaciones"], "Induction reviews": ["Revisões de indução", "Revisiones de inducción"], "Select worker": ["Selecionar trabalhador", "Seleccionar trabajador"],
    "Induction name": ["Nome da indução", "Nombre de la inducción"], "Submit for review": ["Enviar para revisão", "Enviar para revisión"], "Record decision": ["Registar decisão", "Registrar decisión"],
    "Approve": ["Aprovar", "Aprobar"], "Request information": ["Pedir informação", "Solicitar información"], "Decline": ["Recusar", "Rechazar"],
    "Messages": ["Mensagens", "Mensajes"], "Worker conversations": ["Conversas com trabalhadores", "Conversaciones con trabajadores"], "Reply to worker": ["Responder ao trabalhador", "Responder al trabajador"],
    "Inbox": ["Caixa de entrada", "Bandeja"], "Notifications": ["Notificações", "Notificaciones"], "Mark as read": ["Marcar como lida", "Marcar como leída"],
    "Routing": ["Encaminhamento", "Enrutamiento"], "Department contacts": ["Contactos de departamento", "Contactos de departamento"], "Linked user": ["Utilizador associado", "Usuario vinculado"],
    "No linked account": ["Sem conta associada", "Sin cuenta vinculada"], "Add contact": ["Adicionar contacto", "Añadir contacto"], "Deactivate": ["Desativar", "Desactivar"], "Activate": ["Ativar", "Activar"],
    "Delivery": ["Entrega", "Entrega"], "Notification preferences": ["Preferências de notificação", "Preferencias de notificación"],
    "Unavailable channels remain fail-closed until an approved provider is configured.": ["Os canais indisponíveis permanecem bloqueados até existir um fornecedor aprovado.", "Los canales no disponibles permanecen bloqueados hasta configurar un proveedor aprobado."],
    "Available": ["Disponível", "Disponible"], "Unavailable": ["Indisponível", "No disponible"], "Save preferences": ["Guardar preferências", "Guardar preferencias"],
    "Provider approval and configuration required": ["É necessária aprovação e configuração do fornecedor", "Se requiere aprobación y configuración del proveedor"],
    "Administrator": ["Administrador", "Administrador"], "Editor": ["Editor", "Editor"], "Viewer": ["Leitor", "Lector"],
    "Welcome back": ["Bem-vindo de volta", "Bienvenido de nuevo"], "Application sign in": ["Iniciar sessão na aplicação", "Inicio de sesión de la aplicación"],
    "Password": ["Palavra-passe", "Contraseña"], "Sign in": ["Iniciar sessão", "Iniciar sesión"], "Forgot password?": ["Esqueceu a palavra-passe?", "¿Olvidó su contraseña?"],
    "Page not mapped": ["Página não mapeada", "Página no asignada"], "Local route not implemented yet": ["Rota local ainda não implementada", "Ruta local aún no implementada"],
    "Return to Dashboard": ["Voltar ao painel", "Volver al panel"], "System status": ["Estado do sistema", "Estado del sistema"], "Storage": ["Armazenamento", "Almacenamiento"],
    "Healthy": ["Saudável", "Saludable"], "Enabled": ["Ativado", "Activado"], "Disabled": ["Desativado", "Desactivado"], "Read only": ["Só de leitura", "Solo lectura"],
    "Open worker portal": ["Abrir portal do trabalhador", "Abrir portal del trabajador"], "Universal workers": ["Trabalhadores universais", "Trabajadores universales"],
    "Shared documents": ["Documentos partilhados", "Documentos compartidos"], "Integration": ["Integração", "Integración"], "Company API tokens": ["Tokens de API da empresa", "Tokens de API de la empresa"],
    "Primary": ["Principal", "Principal"], "Worker": ["Trabalhador", "Trabajador"], "Site": ["Obra", "Obra"],
    "Administration": ["Administração", "Administración"], "HR": ["Recursos Humanos", "Recursos Humanos"], "Plant": ["Máquinas", "Maquinaria"], "Safety": ["Segurança", "Seguridad"],
    "Additional Information": ["Informação adicional", "Información adicional"], "Approval": ["Aprovação", "Aprobación"], "Certificate Renewal": ["Renovação de certificado", "Renovación de certificado"],
    "Equipment Inspection": ["Inspeção de equipamento", "Inspección de equipo"], "Missing Documents": ["Documentos em falta", "Documentos faltantes"], "New Inspection": ["Nova inspeção", "Nueva inspección"],
    "Other": ["Outro", "Otro"], "Plant Inspection": ["Inspeção de máquinas", "Inspección de maquinaria"], "normal": ["normal", "normal"], "high": ["alta", "alta"], "urgent": ["urgente", "urgente"], "low": ["baixa", "baja"],
    "Conversations begin when a worker-linked request is created.": ["As conversas começam quando é criado um pedido associado a um trabalhador.", "Las conversaciones comienzan al crear una solicitud vinculada a un trabajador."],
    "No contacts configured.": ["Nenhum contacto configurado.", "No hay contactos configurados."], "No tenant migrations have been applied.": ["Nenhuma migração de empresa foi aplicada.", "No se ha aplicado ninguna migración de empresa."],
    "Tenant migration": ["Migração de empresa", "Migración de empresa"], "Authorised migration history": ["Histórico de migrações autorizadas", "Historial de migraciones autorizadas"],
    "Source": ["Origem", "Origen"], "Package": ["Pacote", "Paquete"], "Input": ["Entrada", "Entrada"], "Inserted": ["Inseridos", "Insertados"], "Skipped": ["Ignorados", "Omitidos"], "Authorisation": ["Autorização", "Autorización"],
    "Release readiness, branding, delivery and retention controls": ["Preparação da versão, marca, entrega e controlos de retenção", "Preparación de la versión, marca, entrega y controles de retención"],
    "Database": ["Base de dados", "Base de datos"], "Protected snapshot": ["Cópia protegida", "Copia protegida"], "Immutable imported records": ["Registos importados imutáveis", "Registros importados inmutables"],
    "Local records": ["Registos locais", "Registros locales"], "Controlled writable records": ["Registos editáveis controlados", "Registros editables controlados"],
    "Free storage": ["Armazenamento livre", "Almacenamiento libre"], "Application data filesystem": ["Sistema de ficheiros da aplicação", "Sistema de archivos de la aplicación"],
    "Email delivery": ["Entrega de email", "Entrega de correo"], "Hold": ["Em espera", "En espera"], "Explicitly disabled": ["Explicitamente desativado", "Desactivado explícitamente"],
    "Scheduler": ["Agendador", "Programador"], "Running": ["Em execução", "En ejecución"], "Starting": ["A iniciar", "Iniciando"], "No scheduled run yet": ["Ainda sem execução agendada", "Aún no hay ejecución programada"],
    "Organisation": ["Organização", "Organización"], "Branding and governance": ["Marca e governação", "Marca y gobernanza"],
    "Non-secret settings are stored locally. Environment variables can override them during deployment.": ["As definições não secretas são guardadas localmente. As variáveis de ambiente podem substituí-las na implementação.", "La configuración no secreta se guarda localmente. Las variables de entorno pueden reemplazarla durante el despliegue."],
    "Product name": ["Nome do produto", "Nombre del producto"], "Brand tagline": ["Frase da marca", "Lema de marca"], "Privacy contact": ["Contacto de privacidade", "Contacto de privacidad"],
    "Default compliance recipient": ["Destinatário padrão de conformidade", "Destinatario predeterminado de cumplimiento"], "Reminder window (days)": ["Janela de lembrete (dias)", "Ventana de recordatorio (días)"],
    "Notification retention (days)": ["Retenção de notificações (dias)", "Retención de notificaciones (días)"], "Save settings": ["Guardar definições", "Guardar configuración"], "View privacy notice": ["Ver aviso de privacidade", "Ver aviso de privacidad"],
    "Operations": ["Operações", "Operaciones"], "Delivery and retention": ["Entrega e retenção", "Entrega y retención"],
    "External email remains fail-closed until explicitly enabled in the deployment environment.": ["O email externo permanece bloqueado até ser explicitamente ativado no ambiente de implementação.", "El correo externo permanece bloqueado hasta habilitarlo explícitamente en el entorno de despliegue."],
    "SMTP host": ["Servidor SMTP", "Servidor SMTP"], "Configured": ["Configurado", "Configurado"], "Not configured": ["Não configurado", "No configurado"], "Canonical HTTPS URL": ["URL HTTPS canónico", "URL HTTPS canónica"],
    "Sender": ["Remetente", "Remitente"], "Security": ["Segurança", "Seguridad"], "Queued history": ["Histórico da fila", "Historial de cola"], "Deliver prepared queue": ["Entregar fila preparada", "Entregar cola preparada"],
    "Retention preview": ["Pré-visualização da retenção", "Vista previa de retención"], "Remove expired local data": ["Remover dados locais expirados", "Eliminar datos locales vencidos"],
    "Delivery history": ["Histórico de entrega", "Historial de entrega"], "Prepared and sent notifications": ["Notificações preparadas e enviadas", "Notificaciones preparadas y enviadas"],
    "Date": ["Data", "Fecha"], "Kind": ["Tipo", "Tipo"], "Recipient": ["Destinatário", "Destinatario"], "Attempts": ["Tentativas", "Intentos"], "Action": ["Ação", "Acción"],
    "No local notification history yet.": ["Ainda não existe histórico local de notificações.", "Aún no hay historial local de notificaciones."],
    "Packages are validated and dry-run from the command line before an explicitly authorised apply.": ["Os pacotes são validados e simulados na linha de comandos antes de uma aplicação explicitamente autorizada.", "Los paquetes se validan y simulan desde la línea de comandos antes de una aplicación autorizada explícitamente."]
  };
  const dictionaries = {pt: {}, es: {}};
  Object.entries(entries).forEach(([english, values]) => { dictionaries.pt[english] = values[0]; dictionaries.es[english] = values[1]; });
  const originalText = new WeakMap();
  const originalAttributes = new WeakMap();
  let language = (() => { try { return localStorage.getItem("kompliance_language") || "en"; } catch { return "en"; } })();
  if (!supported.has(language)) language = "en";
  let applying = false;
  const translateValue = (value) => {
    if (language === "en") return value;
    const trimmed = value.trim();
    const direct = dictionaries[language][trimmed];
    if (direct) return value.replace(trimmed, direct);
    const showing = trimmed.match(/^Showing (\d+) to (\d+) of (\d+) entries$/);
    if (showing) return language === "pt" ? `A mostrar ${showing[1]} a ${showing[2]} de ${showing[3]} registos` : `Mostrando ${showing[1]} a ${showing[2]} de ${showing[3]} registros`;
    return value;
  };
  const translateNode = (node) => {
    if (node.nodeType === Node.TEXT_NODE && node.parentElement && !["SCRIPT", "STYLE", "TEXTAREA"].includes(node.parentElement.tagName)) {
      if (!originalText.has(node)) originalText.set(node, node.nodeValue);
      const original = originalText.get(node);
      const translated = language === "en" ? original : translateValue(original);
      if (node.nodeValue !== translated) node.nodeValue = translated;
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const element = node;
    const names = ["placeholder", "title", "aria-label"];
    if (!originalAttributes.has(element)) originalAttributes.set(element, {});
    const originals = originalAttributes.get(element);
    names.forEach(name => {
      if (element.hasAttribute(name) && !(name in originals)) originals[name] = element.getAttribute(name);
      if (name in originals) element.setAttribute(name, language === "en" ? originals[name] : translateValue(originals[name]));
    });
    [...element.childNodes].forEach(translateNode);
  };
  const apply = (root = document.body) => {
    if (!root || applying) return;
    applying = true;
    document.documentElement.lang = language;
    translateNode(root);
    const selector = document.querySelector("#app-language");
    if (selector && selector.value !== language) selector.value = language;
    applying = false;
  };
  const setLanguage = (value, notify = true) => {
    language = supported.has(value) ? value : "en";
    try { localStorage.setItem("kompliance_language", language); } catch {}
    apply(document.body);
    if (notify) window.dispatchEvent(new CustomEvent("kompliance:language", {detail: {language}}));
  };
  const observer = new MutationObserver(mutations => {
    if (applying) return;
    applying = true;
    mutations.forEach(mutation => mutation.addedNodes.forEach(translateNode));
    applying = false;
  });
  window.KomplianceI18n = {apply, setLanguage, getLanguage: () => language, supported: [...supported]};
  document.addEventListener("DOMContentLoaded", () => {
    apply(document.body);
    document.querySelector("#app-language")?.addEventListener("change", event => setLanguage(event.target.value));
    observer.observe(document.body, {childList: true, subtree: true});
  });
})();
