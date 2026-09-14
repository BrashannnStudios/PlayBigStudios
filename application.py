import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List
from database import db

class ApplicationModal(discord.ui.Modal):
    def __init__(self, category: str, questions: List[str], review_channel_id: int):
        super().__init__(title=f"Apply – {category}"[:45])
        self.category = category
        self.review_channel_id = review_channel_id
        self.answers = []

        for i, q in enumerate(questions[:5]):  # Discord modal limit
            self.add_item(discord.ui.TextInput(
                label=q[:45],
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=1000,
                custom_id=f"q{i}"
            ))

    async def on_submit(self, interaction: discord.Interaction):
        answers = [item.value for item in self.children]
        embed = discord.Embed(
            title=f"New Application – {self.category}",
            color=0x57F287,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="User", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)

        for i, (q, a) in enumerate(zip([item.label for item in self.children], answers), 1):
            embed.add_field(name=f"Q{i}: {q}", value=a[:1024], inline=False)

        channel = interaction.guild.get_channel(self.review_channel_id)
        if channel:
            await channel.send(embed=embed)
            await interaction.response.send_message("✅ Your application has been submitted!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Review channel not found. Contact staff.", ephemeral=True)

class CategorySelect(discord.ui.Select):
    def __init__(self, categories: List[str], questions: List[str], review_channel_id: int):
        options = [discord.SelectOption(label=c[:100], value=c) for c in categories[:25]]
        super().__init__(placeholder="Select a category to apply...", options=options, min_values=1, max_values=1)
        self.questions = questions
        self.review_channel_id = review_channel_id

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        modal = ApplicationModal(category, self.questions, self.review_channel_id)
        await interaction.response.send_modal(modal)

class VacantsView(discord.ui.View):
    def __init__(self, categories: List[str], questions: List[str], review_channel_id: int):
        super().__init__(timeout=None)
        self.add_item(CategorySelect(categories, questions, review_channel_id))

class Applications(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="vacants-setup", description="Configure the job application system")
    @app_commands.describe(
        enabled="Enable or disable the system",
        announce_channel="Channel where the vacancies embed will be posted",
        review_channel="Channel where applications will be sent",
        categories="Comma-separated categories (e.g. Developer,Staff,Designer)",
        questions="Questions separated by || (e.g. Why join?||Experience?||Portfolio?)"
    )
    @app_commands.default_permissions(administrator=True)
    async def vacants_setup(
        self,
        interaction: discord.Interaction,
        enabled: bool,
        announce_channel: Optional[discord.TextChannel] = None,
        review_channel: Optional[discord.TextChannel] = None,
        categories: Optional[str] = None,
        questions: Optional[str] = None
    ):
        await interaction.response.defer(ephemeral=True)
        guild_data = await db.get_guild(interaction.guild.id)
        vacants = guild_data["vacants"]

        vacants["enabled"] = enabled
        if announce_channel:
            vacants["announce_channel_id"] = announce_channel.id
        if review_channel:
            vacants["review_channel_id"] = review_channel.id
        if categories is not None:
            vacants["categories"] = [c.strip() for c in categories.split(",") if c.strip()][:25]
        if questions is not None:
            vacants["questions"] = [q.strip() for q in questions.split("||") if q.strip()][:5]

        await db.update_vacants(interaction.guild.id, vacants)

        # Post / update the announce embed if enabled
        if enabled and vacants.get("announce_channel_id") and vacants.get("categories") and vacants.get("questions"):
            channel = interaction.guild.get_channel(vacants["announce_channel_id"])
            if channel:
                embed = discord.Embed(
                    title="🎯 Open Positions – Play BIG Studios",
                    description="We are currently hiring! Select a category below to apply.",
                    color=0x5865F2
                )
                embed.add_field(
                    name="Available Categories",
                    value="\n".join(f"• {c}" for c in vacants["categories"]),
                    inline=False
                )
                embed.set_footer(text="Applications are reviewed by staff")
                view = VacantsView(vacants["categories"], vacants["questions"], vacants["review_channel_id"])
                await channel.send(embed=embed, view=view)

        await interaction.followup.send("✅ Vacants system updated successfully.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Applications(bot))
