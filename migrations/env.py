# migrations/env.py

# ... (Mantenha as importações e configurações iniciais iguais) ...

def run_migrations_online():
    """Run migrations in 'online' mode."""
    
    # ... (Mantenha a função process_revision_directives igual) ...

    conf_args = current_app.extensions['migrate'].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            # ADICIONE ESTA LINHA ABAIXO PARA DETECTAR MUDANÇA DE TIPO:
            compare_type=True, 
            **conf_args
        )

        with context.begin_transaction():
            context.run_migrations()

# ... (Restante do arquivo igual) ...