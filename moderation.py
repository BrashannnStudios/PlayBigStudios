import discord
from discord.ext import commands
from typing import Optional
import time
from database import db

def is_mod():
    async def predicate(ctx: commands.Context):
        if not ctx.guild:
            return False
        perms = ctx.author.guild_permissions
        return perms.administrator or perms.manage_guild or perms.moderate_members
    return commands.check(predicate)

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── Channel Management ─────────────────────────────────────────
    @commands.command(name="lock")
    @is_mod()
    async def lock(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"<:Aceptar:1549130267426300044> {channel.mention} has been locked.")

    @commands.command(name="unlock")
    @is_mod()
    async def unlock(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"<:Aceptar:1549130267426300044> {channel.mention} has been unlocked.")

    @commands.command(name="slowmode")
    @is_mod()
    async def slowmode(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None, seconds: int = 0):
        channel = channel or ctx.channel
        if seconds < 0 or seconds > 21600:
            return await ctx.send("<:DenegadoEmoji:1549130308883058699> Slowmode must be between 0 and 21600 seconds.")
        await channel.edit(slowmode_delay=seconds)
        await ctx.send(f"<:RelojEmoji:1549130376537051176> Slowmode in {channel.mention} set to **{seconds}s**.")

    @commands.command(name="clear")
    @is_mod()
    async def clear(self, ctx: commands.Context, amount: int):
        """Delete a specific amount of messages (max 100)"""
        if amount < 1 or amount > 100:
            return await ctx.send("<:DenegadoEmoji:1549130308883058699> You can only delete between **1** and **100** messages.")

        try:
            deleted = await ctx.channel.purge(limit=amount + 1)  # +1 to include the command message
            msg = await ctx.send(
                f"<:Aceptar:1549130267426300044> Successfully deleted **{len(deleted)-1}** messages.",
                delete_after=5
            )
        except discord.Forbidden:
            await ctx.send("<:DenegadoEmoji:1549130308883058699> I don't have permission to delete messages.")
        except discord.HTTPException:
            await ctx.send("<:DenegadoEmoji:1549130308883058699> Failed to delete messages.")

    # ─── User Info & DM ─────────────────────────────────────────────
    @commands.command(name="userinfo")
    async def userinfo(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        user = user or ctx.author
        embed = discord.Embed(
            title=f"<:Lupaemoji:1549130325488046251> User Info – {user}",
            color=user.color or 0x5865F2
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="ID", value=user.id, inline=True)
        embed.add_field(name="Joined", value=discord.utils.format_dt(user.joined_at, "R") if user.joined_at else "N/A", inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(user.created_at, "R"), inline=True)
        embed.add_field(name="Roles", value=" ".join(r.mention for r in user.roles[1:][:15]) or "None", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="dm")
    @is_mod()
    async def dm(self, ctx: commands.Context, user: discord.Member, *, message: str):
        try:
            await user.send(f"**Message from {ctx.guild.name} staff:**\n{message}")
            await ctx.send(f"<:Aceptar:1549130267426300044> DM sent to {user.mention}.")
        except discord.Forbidden:
            await ctx.send("<:DenegadoEmoji:1549130308883058699> Cannot DM that user (DMs closed or bot blocked).")

    # ─── Mute / Unmute (Timeout) ────────────────────────────────────
    @commands.command(name="mute")
    @is_mod()
    async def mute(self, ctx: commands.Context, user: discord.Member, *, reason: str = "No reason provided"):
        if user.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("<:DenegadoEmoji:1549130308883058699> You cannot mute someone with equal or higher role.")
        try:
            await user.timeout(discord.utils.utcnow() + discord.timedelta(days=28), reason=reason)
            await ctx.send(f"<:AvisoEmoji:1549130289153052762> {user.mention} has been muted.\n**Reason:** {reason}")
        except discord.Forbidden:
            await ctx.send("<:DenegadoEmoji:1549130308883058699> I lack permissions to timeout that user.")

    @commands.command(name="unmute")
    @is_mod()
    async def unmute(self, ctx: commands.Context, user: discord.Member):
        try:
            await user.timeout(None)
            await ctx.send(f"<:Aceptar:1549130267426300044> {user.mention} has been unmuted.")
        except discord.Forbidden:
            await ctx.send("<:DenegadoEmoji:1549130308883058699> I lack permissions to remove timeout.")

    # ─── Ban / Tempban / Unban ──────────────────────────────────────
    @commands.command(name="ban")
    @is_mod()
    async def ban(self, ctx: commands.Context, user: discord.Member, *, reason: str = "No reason provided"):
        if user.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("<:DenegadoEmoji:1549130308883058699> You cannot ban someone with equal or higher role.")
        try:
            await user.ban(reason=reason, delete_message_days=0)
            await ctx.send(f"<:Aceptar:1549130267426300044> {user} has been banned.\n**Reason:** {reason}")
        except discord.Forbidden:
            await ctx.send("<:DenegadoEmoji:1549130308883058699> I lack permissions to ban that user.")

    @commands.command(name="tempban")
    @is_mod()
    async def tempban(self, ctx: commands.Context, user: discord.Member, duration: str, *, reason: str = "No reason provided"):
        """Duration examples: 1h, 2d, 7d, 30d"""
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        try:
            amount = int(duration[:-1])
            unit = duration[-1].lower()
            seconds = amount * units[unit]
        except (ValueError, KeyError):
            return await ctx.send("<:DenegadoEmoji:1549130308883058699> Invalid duration. Use e.g. `1h`, `2d`, `7d`.")

        if user.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("<:DenegadoEmoji:1549130308883058699> You cannot ban someone with equal or higher role.")

        until = int(time.time()) + seconds
        try:
            await user.ban(reason=f"[TEMP] {reason} | Until: {until}", delete_message_days=0)
            await db.set_tempban(ctx.guild.id, user.id, until, reason)
            await ctx.send(
                f"<:RelojArenaEmoji:1549130360011493426> {user} has been temporarily banned for **{duration}**.\n"
                f"**Reason:** {reason}"
            )
        except discord.Forbidden:
            await ctx.send("<:DenegadoEmoji:1549130308883058699> I lack permissions to ban that user.")

    @commands.command(name="unban")
    @is_mod()
    async def unban(self, ctx: commands.Context, user_id: int, *, reason: str = "No reason provided"):
        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user, reason=reason)
            await db.clear_tempban(ctx.guild.id, user_id)
            await ctx.send(f"<:Aceptar:1549130267426300044> {user} has been unbanned.\n**Reason:** {reason}")
        except discord.NotFound:
            await ctx.send("<:DenegadoEmoji:1549130308883058699> User is not banned or ID is invalid.")
        except discord.Forbidden:
            await ctx.send("<:DenegadoEmoji:1549130308883058699> I lack permissions to unban.")

    # ─── Notes ──────────────────────────────────────────────────────
    @commands.command(name="addnote")
    @is_mod()
    async def addnote(self, ctx: commands.Context, user: discord.Member, *, note: str):
        note_id = await db.add_note(ctx.guild.id, user.id, note, ctx.author.id)
        await ctx.send(f"<:PlumaEmoji:1549130341610950706> Note `#{note_id}` added to {user.mention}.")

    @commands.command(name="removenote")
    @is_mod()
    async def removenote(self, ctx: commands.Context, user: discord.Member, note_id: int):
        success = await db.remove_note(ctx.guild.id, user.id, note_id)
        if success:
            await ctx.send(f"<:Aceptar:1549130267426300044> Note `#{note_id}` removed from {user.mention}.")
        else:
            await ctx.send("<:DenegadoEmoji:1549130308883058699> Note not found.")

    @commands.command(name="viewnotes")
    @is_mod()
    async def viewnotes(self, ctx: commands.Context, user: discord.Member):
        data = await db.get_user(ctx.guild.id, user.id)
        notes = data.get("notes", [])
        if not notes:
            return await ctx.send(f"<:Lupaemoji:1549130325488046251> No notes for {user.mention}.")
        embed = discord.Embed(
            title=f"<:PlumaEmoji:1549130341610950706> Notes – {user}",
            color=0xFEE75C
        )
        for n in notes[-10:]:
            embed.add_field(
                name=f"#{n['id']} • <t:{n['timestamp']}:R>",
                value=f"{n['content'][:200]}\n*by <@{n['moderator_id']}>*",
                inline=False
            )
        await ctx.send(embed=embed)

    # ─── Warns ──────────────────────────────────────────────────────
    @commands.command(name="warn")
    @is_mod()
    async def warn(self, ctx: commands.Context, user: discord.Member, *, reason: str):
        warn_id = await db.add_warn(ctx.guild.id, user.id, reason, ctx.author.id)
        await ctx.send(
            f"<:AvisoEmoji:1549130289153052762> {user.mention} has been warned (`#{warn_id}`).\n"
            f"**Reason:** {reason}"
        )
        try:
            await user.send(f"<:AvisoEmoji:1549130289153052762> You received a warning in **{ctx.guild.name}**:\n{reason}")
        except discord.Forbidden:
            pass

    @commands.command(name="delwarn")
    @is_mod()
    async def delwarn(self, ctx: commands.Context, user: discord.Member, warn_id: int):
        success = await db.remove_warn(ctx.guild.id, user.id, warn_id)
        if success:
            await ctx.send(f"<:Aceptar:1549130267426300044> Warn `#{warn_id}` removed from {user.mention}.")
        else:
            await ctx.send("<:DenegadoEmoji:1549130308883058699> Warn not found.")

    # ─── Help / Commands List ───────────────────────────────────────
@commands.command(name="cmds")
async def cmds(self, ctx: commands.Context):
    embed = discord.Embed(
        title="<:Lupaemoji:1549130325488046251> Play BIG Studios — Commands",
        color=0x5865F2
    )

    # Columna 1
    embed.add_field(
        name="🛠️ Moderation",
        value=(
            "`?lock` `?unlock`\n"
            "`?slowmode` `?clear`\n"
            "`?mute` `?unmute`\n"
            "`?ban` `?tempban`\n"
            "`?unban`"
        ),
        inline=True
    )

    # Columna 2
    embed.add_field(
        name="<:AvisoEmoji:1549130289153052762> Warns & Notes",
        value=(
            "`?warn` `?delwarn`\n"
            "`?addnote`\n"
            "`?removenote`\n"
            "`?viewnotes`"
        ),
        inline=True
    )

    # Columna 3
    embed.add_field(
        name="<:Lupaemoji:1549130325488046251> Utility",
        value=(
            "`?userinfo`\n"
            "`?dm`\n"
            "`?cmds`"
        ),
        inline=True
    )

    # Configuración abajo (ocupa todo el ancho)
    embed.add_field(
        name="⚙️ Configuration (Slash)",
        value="`/welcome-setup`  •  `/vacants-setup`",
        inline=False
    )

    embed.set_footer(text="Play BIG Studios • Dev: Supskevv")
    await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
