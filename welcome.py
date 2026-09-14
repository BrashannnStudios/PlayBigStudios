import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List
from database import db

class WelcomeView(discord.ui.View):
    def __init__(self, links: List[dict]):
        super().__init__(timeout=None)
        for link in links[:5]:  # Discord limit 5 buttons
            self.add_item(discord.ui.Button(
                label=link["label"][:80],
                url=link["url"],
                style=discord.ButtonStyle.link
            ))

class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        guild_data = await db.get_guild(member.guild.id)
        welcome = guild_data.get("welcome", {})
        if not welcome.get("enabled") or not welcome.get("channel_id"):
            return

        channel = member.guild.get_channel(welcome["channel_id"])
        if not channel:
            return

        message = welcome.get("message", "Welcome {user} to **{server}**!")
        message = message.replace("{user}", member.mention).replace("{server}", member.guild.name)

        embed = discord.Embed(
            description=message,
            color=welcome.get("color", 0x5865F2)
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)

        if welcome.get("image"):
            embed.set_image(url=welcome["image"])

        rec = welcome.get("recommended_channels", [])
        if rec:
            channels_text = "\n".join(f"• <#{cid}>" for cid in rec if member.guild.get_channel(cid))
            if channels_text:
                embed.add_field(name="Recommended Channels", value=channels_text, inline=False)

        view = WelcomeView(welcome.get("links", [])) if welcome.get("links") else None
        try:
            await channel.send(content=member.mention, embed=embed, view=view)
        except discord.HTTPException:
            pass

    @app_commands.command(name="welcome-setup", description="Configure the welcome system")
    @app_commands.describe(
        enabled="Enable or disable the welcome system",
        channel="Channel where welcome embeds will be sent",
        message="Welcome message. Use {user} and {server}",
        color="Hex color (e.g. #5865F2)",
        image="Optional image/GIF URL",
        recommended="Comma-separated channel IDs (e.g. 123,456)",
        links="Optional links as label|url,label|url"
    )
    @app_commands.default_permissions(administrator=True)
    async def welcome_setup(
        self,
        interaction: discord.Interaction,
        enabled: bool,
        channel: Optional[discord.TextChannel] = None,
        message: Optional[str] = None,
        color: Optional[str] = None,
        image: Optional[str] = None,
        recommended: Optional[str] = None,
        links: Optional[str] = None
    ):
        await interaction.response.defer(ephemeral=True)
        guild_data = await db.get_guild(interaction.guild.id)
        welcome = guild_data["welcome"]

        welcome["enabled"] = enabled
        if channel:
            welcome["channel_id"] = channel.id
        if message:
            welcome["message"] = message[:2000]
        if color:
            try:
                welcome["color"] = int(color.lstrip("#"), 16)
            except ValueError:
                return await interaction.followup.send("Invalid color format. Use #RRGGBB", ephemeral=True)
        if image is not None:
            welcome["image"] = image if image else None
        if recommended is not None:
            try:
                welcome["recommended_channels"] = [int(x.strip()) for x in recommended.split(",") if x.strip()]
            except ValueError:
                return await interaction.followup.send("Invalid channel IDs", ephemeral=True)
        if links is not None:
            parsed = []
            if links.strip():
                for part in links.split(","):
                    if "|" in part:
                        label, url = part.split("|", 1)
                        if url.startswith("http"):
                            parsed.append({"label": label.strip()[:80], "url": url.strip()})
            welcome["links"] = parsed

        await db.update_welcome(interaction.guild.id, welcome)
        await interaction.followup.send("✅ Welcome system updated successfully.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
