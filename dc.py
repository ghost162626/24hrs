import discord
from discord import Embed
from datetime import datetime, timedelta
import asyncio
import requests
import json
import random
import string

# Configuração do bot Discord
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

PREFIX = '!'

# Configuração do Firebase
FIREBASE_URL = "https://coderaw-2025-default-rtdb.firebaseio.com"

def get_raw_from_firebase(raw_id):
    """Busca um raw específico do Firebase"""
    url = f"{FIREBASE_URL}/raws/{raw_id}.json"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        print(f"Erro ao buscar raw: {e}")
        return None

def update_raw_in_firebase(raw_id, new_code):
    """Atualiza o código de um raw no Firebase"""
    url = f"{FIREBASE_URL}/raws/{raw_id}/code.json"
    
    try:
        response = requests.put(url, data=json.dumps(new_code))
        return response.status_code == 200
    except Exception as e:
        print(f"Erro ao atualizar raw: {e}")
        return False

def parse_datetime(date_obj):
    """Converte datetime para formato Lua"""
    return f'os.time({{day={date_obj.day}, month={date_obj.month}, year={date_obj.year}, hour={date_obj.hour}, min={date_obj.minute}}})'

def add_whitelist_to_code(existing_code, player_id, player_name, added_by, expires_date):
    """Adiciona uma linha de whitelist ao código existente"""
    
    # Verificar se o código já tem a estrutura de return
    if "return" in existing_code and "{" in existing_code:
        # Encontrar a última chave antes de fechar
        lines = existing_code.split('\n')
        new_lines = []
        
        added = False
        for i, line in enumerate(lines):
            new_lines.append(line)
            # Se encontrar a linha com apenas "}" (fechamento do return)
            if line.strip() == "}" and not added:
                # Adicionar a nova whitelist antes do fechamento
                new_line = f'    ["{player_id}"] = {{type = "Usuário adm", expires = {parse_datetime(expires_date)}}},'
                new_lines.insert(i, new_line)
                added = True
        
        return '\n'.join(new_lines)
    else:
        # Se não tem estrutura, criar uma nova
        return f'''-- Whitelist adicionada por {added_by}
-- Data: {datetime.now().strftime("%d/%m/%Y %H:%M")}

return {{
    ["{player_id}"] = {{type = "Usuário adm", expires = {parse_datetime(expires_date)}}},
}}'''

def remove_whitelist_from_code(existing_code, player_id):
    """Remove uma whitelist do código"""
    lines = existing_code.split('\n')
    new_lines = []
    
    skip_next = False
    for i, line in enumerate(lines):
        # Verificar se esta linha contém o player_id que queremos remover
        if f'["{player_id}"]' in line:
            skip_next = True
            continue
        elif skip_next and line.strip().startswith("}"):
            skip_next = False
            new_lines.append(line)
        elif not skip_next:
            new_lines.append(line)
    
    return '\n'.join(new_lines)

@client.event
async def on_ready():
    print(f'🤖 Bot conectado como {client.user}')
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="!help"))

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    if not message.content.startswith(PREFIX):
        return

    args = message.content[len(PREFIX):].split()
    command = args[0].lower() if args else ""

    # Comando: !addwhitelist <raw_id> -player <playerId> -days <dias>
    if command == "addwhitelist":
        try:
            # Parse dos argumentos
            raw_id = None
            player_id = None
            days = 30  # default

            i = 1
            while i < len(args):
                if args[i] == "-player" and i + 1 < len(args):
                    player_id = args[i + 1]
                    i += 2
                elif args[i] == "-days" and i + 1 < len(args):
                    days = int(args[i + 1])
                    i += 2
                elif not raw_id:  # O primeiro argumento que não é -player ou -days é o raw_id
                    raw_id = args[i]
                    i += 1
                else:
                    i += 1

            if not raw_id or not player_id:
                embed = Embed(
                    title="❌ Uso incorreto",
                    description="**Uso correto:** `!addwhitelist <raw_id> -player <playerId> -days <dias>`\n**Exemplo:** `!addwhitelist -OcfVWoCNOj7-B-kxUO8 -player 123456 -days 30`",
                    color=0xff0000
                )
                await message.reply(embed=embed)
                return

            # Buscar o raw existente no Firebase
            raw_data = get_raw_from_firebase(raw_id)
            
            if not raw_data:
                embed = Embed(
                    title="❌ Raw não encontrado",
                    description=f"Raw com ID `{raw_id}` não foi encontrado no Firebase.",
                    color=0xff0000
                )
                await message.reply(embed=embed)
                return

            # Calcular data de expiração
            now = datetime.now()
            expires_date = now + timedelta(days=days)
            player_name = f"Player_{player_id}"

            # Obter código atual
            current_code = raw_data.get("code", "")
            current_title = raw_data.get("title", "Raw sem título")

            # Adicionar whitelist ao código existente
            new_code = add_whitelist_to_code(
                current_code, 
                player_id, 
                player_name, 
                str(message.author), 
                expires_date
            )

            # Atualizar no Firebase
            success = update_raw_in_firebase(raw_id, new_code)

            if not success:
                embed = Embed(
                    title="❌ Erro Firebase",
                    description="Não foi possível atualizar o raw no Firebase.",
                    color=0xff0000
                )
                await message.reply(embed=embed)
                return

            # Embed de confirmação
            embed1 = Embed(
                title="✅ Whitelist Adicionada",
                color=0x00ff00,
                timestamp=now
            )
            embed1.add_field(name="📝 Raw", value=f"`{current_title}`", inline=True)
            embed1.add_field(name="🆔 Raw ID", value=f"`{raw_id}`", inline=True)
            embed1.add_field(name="🎮 Player ID", value=f"`{player_id}`", inline=True)
            embed1.add_field(name="👤 Player Name", value=player_name, inline=True)
            embed1.add_field(name="⏰ Expira em", value=f"<t:{int(expires_date.timestamp())}:R>", inline=True)
            embed1.add_field(name="📝 Adicionado por", value=str(message.author), inline=True)
            embed1.set_footer(text="CodeRaw 2025 - Sistema de Whitelist")

            # Embed do código (apenas a parte nova)
            new_whitelist_line = f'    ["{player_id}"] = {{type = "Usuário adm", expires = {parse_datetime(expires_date)}}},'
            code_preview = f"-- Linha adicionada:\n{new_whitelist_line}"
            
            embed2 = Embed(
                title="📄 Whitelist Adicionada",
                description=f"```lua\n{code_preview}\n```",
                color=0x0099ff,
                timestamp=now
            )

            await message.reply(embeds=[embed1, embed2])

        except Exception as e:
            print(f"Erro: {e}")
            embed = Embed(
                title="❌ Erro",
                description=f"Erro: {str(e)}",
                color=0xff0000
            )
            await message.reply(embed=embed)

    # Comando: !removewhitelist <raw_id> -player <playerId>
    elif command == "removewhitelist":
        try:
            raw_id = None
            player_id = None

            i = 1
            while i < len(args):
                if args[i] == "-player" and i + 1 < len(args):
                    player_id = args[i + 1]
                    i += 2
                elif not raw_id:
                    raw_id = args[i]
                    i += 1
                else:
                    i += 1

            if not raw_id or not player_id:
                embed = Embed(
                    title="❌ Uso incorreto",
                    description="**Uso correto:** `!removewhitelist <raw_id> -player <playerId>`\n**Exemplo:** `!removewhitelist -OcfVWoCNOj7-B-kxUO8 -player 123456`",
                    color=0xff0000
                )
                await message.reply(embed=embed)
                return

            # Buscar o raw existente
            raw_data = get_raw_from_firebase(raw_id)
            
            if not raw_data:
                embed = Embed(
                    title="❌ Raw não encontrado",
                    description=f"Raw com ID `{raw_id}` não foi encontrado.",
                    color=0xff0000
                )
                await message.reply(embed=embed)
                return

            current_code = raw_data.get("code", "")
            current_title = raw_data.get("title", "Raw sem título")

            # Remover whitelist
            new_code = remove_whitelist_from_code(current_code, player_id)

            # Atualizar no Firebase
            success = update_raw_in_firebase(raw_id, new_code)

            if not success:
                embed = Embed(
                    title="❌ Erro Firebase",
                    description="Não foi possível atualizar o raw.",
                    color=0xff0000
                )
                await message.reply(embed=embed)
                return

            embed = Embed(
                title="✅ Whitelist Removida",
                color=0x00ff00,
                timestamp=datetime.now()
            )
            embed.add_field(name="📝 Raw", value=current_title, inline=True)
            embed.add_field(name="🆔 Raw ID", value=f"`{raw_id}`", inline=True)
            embed.add_field(name="🎮 Player ID", value=f"`{player_id}`", inline=True)
            embed.add_field(name="🗑️ Removido por", value=str(message.author), inline=True)
            embed.set_footer(text="CodeRaw 2025 - Sistema de Whitelist")

            await message.reply(embed=embed)

        except Exception as e:
            print(f"Erro: {e}")
            embed = Embed(
                title="❌ Erro",
                description=f"Erro: {str(e)}",
                color=0xff0000
            )
            await message.reply(embed=embed)

    # Comando: !viewraw <raw_id>
    elif command == "viewraw":
        if len(args) < 2:
            await message.reply("❌ **Uso:** `!viewraw <raw_id>`")
            return

        raw_id = args[1]
        try:
            raw_data = get_raw_from_firebase(raw_id)
            
            if not raw_data:
                await message.reply("❌ Raw não encontrado.")
                return

            embed = Embed(
                title=f"📄 {raw_data.get('title', 'Raw')}",
                color=0x0099ff,
                timestamp=datetime.now()
            )
            embed.add_field(name="🆔 ID", value=f"`{raw_id}`", inline=True)
            embed.add_field(name="👤 Autor", value=raw_data.get("authorName", "Desconhecido"), inline=True)
            embed.add_field(name="👀 Views", value=raw_data.get("views", 0), inline=True)
            
            # Mostrar preview do código
            code = raw_data.get("code", "")
            code_preview = code if len(code) <= 1000 else code[:1000] + "..."
            
            code_embed = Embed(
                title="📄 Código",
                description=f"```lua\n{code_preview}\n```",
                color=0xffa500,
                timestamp=datetime.now()
            )

            await message.reply(embeds=[embed, code_embed])

        except Exception as e:
            print(f"Erro: {e}")
            await message.reply("❌ Erro ao buscar raw.")

    # Comando: !listwhitelist <raw_id>
    elif command == "listwhitelist":
        if len(args) < 2:
            await message.reply("❌ **Uso:** `!listwhitelist <raw_id>`")
            return

        raw_id = args[1]
        try:
            raw_data = get_raw_from_firebase(raw_id)
            
            if not raw_data:
                await message.reply("❌ Raw não encontrado.")
                return

            code = raw_data.get("code", "")
            lines = code.split('\n')
            
            whitelist_entries = []
            for line in lines:
                if '["' in line and 'type = "Usuário adm"' in line:
                    # Extrair player ID da linha
                    player_id = line.split('["')[1].split('"]')[0]
                    whitelist_entries.append(player_id)

            embed = Embed(
                title=f"📋 Whitelist - {raw_data.get('title', 'Raw')}",
                color=0x7289da,
                timestamp=datetime.now()
            )
            
            if whitelist_entries:
                embed.description = f"**Total de usuários na whitelist:** {len(whitelist_entries)}"
                # Mostrar os primeiros 10 usuários
                users_text = "\n".join([f"• `{user_id}`" for user_id in whitelist_entries[:10]])
                if len(whitelist_entries) > 10:
                    users_text += f"\n... e mais {len(whitelist_entries) - 10} usuários"
                embed.add_field(name="👥 Usuários", value=users_text, inline=False)
            else:
                embed.description = "Nenhum usuário na whitelist."

            embed.set_footer(text=f"Raw ID: {raw_id}")

            await message.reply(embed=embed)

        except Exception as e:
            print(f"Erro: {e}")
            await message.reply("❌ Erro ao listar whitelist.")

    # Comando: !help
    elif command == "help":
        embed = Embed(
            title="🤖 Comandos do CodeRaw Whitelist Bot",
            color=0x7289da,
            timestamp=datetime.now()
        )
        embed.description = "Sistema de gerenciamento de whitelist em raws"
        embed.add_field(
            name="➕ Adicionar Whitelist",
            value="`!addwhitelist <raw_id> -player <playerId> -days <dias>`\nAdiciona whitelist a um raw\n**Exemplo:** `!addwhitelist -OcfVWoCNOj7-B-kxUO8 -player 123456 -days 30`",
            inline=False
        )
        embed.add_field(
            name="🗑️ Remover Whitelist",
            value="`!removewhitelist <raw_id> -player <playerId>`\nRemove usuário da whitelist\n**Exemplo:** `!removewhitelist -OcfVWoCNOj7-B-kxUO8 -player 123456`",
            inline=False
        )
        embed.add_field(
            name="📋 Listar Whitelist",
            value="`!listwhitelist <raw_id>`\nMostra todos os usuários na whitelist",
            inline=False
        )
        embed.add_field(
            name="👀 Ver Raw",
            value="`!viewraw <raw_id>`\nMostra informações e código de um raw",
            inline=False
        )
        embed.set_footer(text="CodeRaw 2025 - Sistema de Whitelist")

        await message.reply(embed=embed)

# Executar o bot
if __name__ == "__main__":
    client.run('MTQzMjc1ODkzMzk4MjAxOTcyOQ.GCjfVq.GcLfrHVjrXfn93DCdmDSkfefEPjmerK4N_ld8A')
