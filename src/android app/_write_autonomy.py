import os

# Part 1: AutonomyScreen.kt - data classes and basic structure
path = 'app/src/main/kotlin/com/friday/remote/ui/screens/AutonomyScreen.kt'

content = '''package com.friday.remote.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.friday.remote.network.FridaySocketManager
import com.friday.remote.ui.theme.FridayAccent
import com.friday.remote.ui.theme.FridayGrey

@Composable
fun AutonomyScreen(socketManager: FridaySocketManager) {
    val status by socketManager.autonomyStatus.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text(
            text = "Autonomy",
            style = MaterialTheme.typography.titleLarge,
            color = Color.White,
            modifier = Modifier.padding(bottom = 16.dp)
        )

        val phases = status?.phases
        if (phases != null && phases.isNotEmpty()) {
            Text(
                text = "Pipeline Phases",
                color = Color.LightGray,
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(bottom = 8.dp)
            )
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                phases.forEach { (phase, state) ->
                    PhaseRow(phase, state)
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
        }

        val proposals = status?.proposals
        if (!proposals.isNullOrEmpty()) {
            Text(
                text = "Pending Proposals (" + proposals.size + ")",
                color = Color.LightGray,
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(bottom = 8.dp)
            )
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(proposals, key = { it.id }) { proposal ->
                    ProposalCard(proposal, socketManager)
                }
            }
        } else if (phases != null) {
            Text(
                text = "No pending proposals",
                color = Color.LightGray,
                fontSize = 13.sp,
                modifier = Modifier.padding(top = 16.dp)
            )
        }
'''

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Part 1 written')
part2 = """
        val findings = status?.securityFindings
        if (!findings.isNullOrEmpty()) {
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "Security Findings (" + findings.size + ")",
                color = Color(0xFFFF5252),
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(bottom = 8.dp)
            )
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(findings, key = { it.path + it.value }) { finding ->
                    SecurityFindingCard(finding, socketManager)
                }
            }
        }

        val error = status?.error
        if (!error.isNullOrEmpty()) {
            Text(
                text = error,
                color = Color(0xFFFF5252),
                fontSize = 13.sp,
                modifier = Modifier.padding(top = 16.dp)
            )
        }
    }
}

@Composable
fun PhaseRow(phase: String, state: String) {
    val color = when (state) {
        "complete" -> Color(0xFF4CAF50)
        "blocked" -> Color(0xFFFF9800)
        "pending" -> FridayAccent
        "approval_required" -> Color(0xFFFF9800)
        "none" -> Color.LightGray
        else -> Color.LightGray
    }
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = phase.replace("_", " "),
            color = Color.White,
            fontSize = 14.sp
        )
        Text(
            text = state,
            color = color,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold
        )
    }
}

@Composable
fun ProposalCard(proposal: FridaySocketManager.AutonomyProposal, socketManager: FridaySocketManager) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = FridayGrey),
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                text = proposal.name,
                color = Color.White,
                fontWeight = FontWeight.Bold,
                fontSize = 16.sp
            )
            Text(
                text = "Kind: " + proposal.kind,
                color = Color.LightGray,
                fontSize = 12.sp,
                modifier = Modifier.padding(top = 4.dp)
            )
            Text(
                text = proposal.reason,
                color = Color.LightGray,
                fontSize = 13.sp,
                modifier = Modifier.padding(top = 4.dp)
            )
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
                horizontalArrangement = Arrangement.End,
                verticalAlignment = Alignment.CenterVertically
            ) {
                TextButton(onClick = { }) {
                    Text("Details", color = Color.LightGray, fontSize = 12.sp)
                }
                Spacer(modifier = Modifier.width(8.dp))
                Button(
                    onClick = { socketManager.approveAutonomyProposal(proposal.id) },
                    colors = ButtonDefaults.buttonColors(containerColor = FridayAccent),
                    modifier = Modifier.height(32.dp)
                ) {
                    Text("Approve", color = Color.Black, fontSize = 12.sp)
                }
            }
        }
    }
}

@Composable
fun SecurityFindingCard(finding: FridaySocketManager.SecurityFinding, socketManager: FridaySocketManager) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF2A1A1A)),
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                text = finding.path,
                color = Color.White,
                fontWeight = FontWeight.Bold,
                fontSize = 14.sp
            )
            Text(
                text = finding.value,
                color = Color.LightGray,
                fontSize = 12.sp,
                modifier = Modifier.padding(top = 4.dp)
            )
            TextButton(
                onClick = { socketManager.resolveSecurityFinding(finding.path, finding.value) },
                modifier = Modifier.align(Alignment.End)
            ) {
                Text("Resolve", color = FridayAccent, fontSize = 12.sp)
            }
        }
    }
}
"""

path = "app/src/main/kotlin/com/friday/remote/ui/screens/AutonomyScreen.kt"
with open(path, "a", encoding="utf-8") as f:
    f.write(part2)
print("Part 2 appended")
